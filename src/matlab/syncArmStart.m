function syncArmStart(src, evt, varargin)
% syncArmStart (v4) — DoTask-based ALS-safe injector arm.
% =========================================================================
% WHY v4: the generic WaveformGenerator cannot arm under ALS (startTask ->
%   computeWaveform -> linePeriod asserts ImagingField -> fails on the ALS
%   StimulusField). v4 bypasses the WG and drives D3.2 with a low-level
%   dabs.vidrio.ddi.rdi.DoTask, which never touches scannerset/linePeriod.
%
% MECHANISM (confirmed API + props + live test, 2026-06-17):
%   addChannel('D3.2','injTrig',0)        % idle LOW
%   convertToBufferedTask()               % on-demand -> buffered (REQUIRED)
%   sampleRate = R_Hz  (property)         % cfgSampClkTiming() throws 'not done' -> AVOID
%   sampleMode      = 'finite'            % override the 'continuous' default
%   samplesPerTrigger = nSamp             % one buffer playback per trigger
%   writeOutputBuffer(pulseVec)           % length = nSamp
%   cfgDigEdgeStartTrig('/vDAQ0/D2.2')    % edge = rising (default prop)
%   start()                               % arm; latches FIRST D2.2 edge
%   allowRetrigger=0 (default) -> only the first frame-clock edge fires it.
%
%   The pulse lands at ALS cycle N because the buffer's leading zeros encode
%   N*cycle_period of delay at R_Hz; the start trigger latches cycle 0.
%   DETERMINISM PRECONDITION: start() completes before the first frame-clock
%   edge (head_pad ~2.2-3.5 s gives margin). Verify by cycle agreement >=3 runs.
%
% PREREQS (ONCE, by hand): (1) Remove WG 'TrigLegato130-2' in Resource Config
%   to FREE D3.2 (else start()/reserve fails on the reservation).
%   (2) Wiring: D3.2->T->AI7(+Legato+D2.1); D0.0->T->AI6 + D2.2.
%   (3) Run sync_v4_probe.m once to confirm the output path.
%
% REGISTER: acqModeStart -> syncArmStart ; acqAbort+acqDone -> syncDisarm.
%   frameAcquired stays EMPTY.
% TUNING: edit syncParams() OR override at runtime:
%   setappdata(0,'sync_v4_params', struct('N',800,'R_Hz',1e5))
% NOTE (2026-06-19): cycle_period_s now auto-reads the LIVE ALS cycle from hSI
%   (hRoiManager.scanFramePeriod, via alsCyclePeriodS) instead of a hardcoded
%   8 ms. An override that disagrees with the live scanner logs a warning at arm.
% =========================================================================
    APPKEY = 'sync_v4_task';
    try
        p = syncParams();

        % --- clean up any stale task (re-construct each run) -----------------
        old = getappdata(0, APPKEY);
        if ~isempty(old) && isvalid(old)
            try, old.abort(); catch, end
            try, delete(old);  catch, end
        end
        setappdata(0, APPKEY, []);

        % --- hDAQ ------------------------------------------------------------
        hDAQ = i_getVdaq(p.daq_name);

        % --- pulse buffer ----------------------------------------------------
        lead = round(p.N * p.cycle_period_s * p.R_Hz);   % delay to cycle N
        high = round(p.pulse_width_s * p.R_Hz);          % HIGH width
        tail = round(p.tail_s * p.R_Hz);                 % ends buffer LOW
        pulseVec = [zeros(lead,1); ones(high,1); zeros(tail,1)];
        nSamp = numel(pulseVec);

        % --- construct + arm (CONFIRMED API) ---------------------------------
        hT = dabs.vidrio.ddi.rdi.DoTask.createDoTask(hDAQ, 'injTrig');
        hT.addChannel(p.do_chan, 'injTrig', 0);   % idle LOW
        hT.convertToBufferedTask();               % on-demand -> buffered (required)
        hT.sampleRate = p.R_Hz;                   % rate via property (cfgSampClkTiming = 'not done')
        hT.sampleMode = 'finite';                 % override continuous default
        hT.samplesPerTrigger = nSamp;             % one playback per trigger
        hT.writeOutputBuffer(pulseVec);
        hT.cfgDigEdgeStartTrig(p.trigger_term);   % edge rising (default prop)
        hT.start();                               % arm: waits for D2.2

        % --- persist handle + params actually used ---------------------------
        setappdata(0, APPKEY, hT);
        setappdata(0, 'sync_v4_armed', struct( ...
            'N', p.N, 'R_Hz', p.R_Hz, 'cycle_period_s', p.cycle_period_s, ...
            'pulse_width_s', p.pulse_width_s, 'nSamp', nSamp, ...
            'sampleMode', char(hT.sampleMode), ...
            'trigger_term', p.trigger_term, 'do_chan', p.do_chan, ...
            't_arm', datestr(now,'yyyy-mm-dd HH:MM:SS')));

        fprintf(['[sync] armed DoTask on %s (%s), trig %s/%s, ' ...
                 'target cycle N=%d (cyc %.4f ms, R=%.0f Hz, nSamp=%d, ~%.3fs delay)\n'], ...
                 p.do_chan, char(hT.sampleMode), p.trigger_term, ...
                 string(hT.startTriggerEdge), p.N, p.cycle_period_s*1e3, ...
                 p.R_Hz, nSamp, lead/p.R_Hz);
    catch ME
        fprintf(2, '[sync] DoTask ARM FAILED: %s\n', ME.message);
        if ~isempty(ME.stack)
            fprintf(2, '       at %s line %d\n', ME.stack(1).name, ME.stack(1).line);
        end
    end
end

% =========================================================================
function p = syncParams()
% Defaults. cycle_period_s is auto-read from the LIVE hSI ALS cycle
% (hRoiManager.scanFramePeriod, via alsCyclePeriodS; was hardcoded 8 ms).
% Override any field via setappdata(0,'sync_v4_params', struct(...)).
    live_cyc = alsCyclePeriodS([], 8.0e-3);      % live ALS cycle [s]; fallback 8 ms
    p = struct( ...
        'daq_name',       'vDAQ0',          ...
        'do_chan',        'D3.2',           ...
        'trigger_term',   '/vDAQ0/D2.2',    ...  % frame-clock T-split (rising)
        'cycle_period_s', live_cyc,         ...  % auto from hSI.hRoiManager.scanFramePeriod
        'N',              500,              ...  % target ALS cycle
        'R_Hz',           1e5,              ...  % DoTask sample clock (modest)
        'pulse_width_s',  0.15,             ...  % ~0.1-0.2 s
        'tail_s',         0.05);                 % return-to-low margin
    ov = getappdata(0, 'sync_v4_params');
    if ~isempty(ov) && isstruct(ov)
        f = fieldnames(ov);
        for k = 1:numel(f), p.(f{k}) = ov.(f{k}); end
    end
    % surface drift: never let a stale override silently mistime the injection
    if abs(p.cycle_period_s - live_cyc) > 0.01*live_cyc
        warning(['[sync] cycle_period override %.4f s != live hSI %.4f s ' ...
                 '(N=%d will land at the OVERRIDE timing)'], ...
                 p.cycle_period_s, live_cyc, p.N);
    end
end

% =========================================================================
function hDAQ = i_getVdaq(name)
    rs = dabs.resources.ResourceStore();
    hDAQ = rs.filterByName(name);             % confirmed: returns vDAQR1
    if iscell(hDAQ), if ~isempty(hDAQ), hDAQ = hDAQ{1}; end; end
    if isempty(hDAQ)                          % fallback: borrow from a WG
        try
            wgs = rs.filterByClass('dabs.generic.WaveformGenerator');
            if ~isempty(wgs), hDAQ = wgs{1}.hDAQ; end
        catch, end
    end
    assert(~isempty(hDAQ), '[sync] vDAQ "%s" not found.', name);
end
