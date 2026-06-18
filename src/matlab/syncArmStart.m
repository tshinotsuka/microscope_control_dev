function syncArmStart(src, evt, varargin)
% syncArmStart (v4) — DoTask-based ALS-safe injector arm.
% =========================================================================
% WHY v4 (vs v3 = WaveformGenerator):
%   The generic WaveformGenerator CANNOT arm under ALS. startTask ->
%   updateWaveform -> computeWaveform -> refreshWvfmParams ->
%   scannerset.linePeriod -> GalvoGalvo.linePeriod (489) asserts the
%   scanfield is an ImagingField -> FAILS for the ALS StimulusField.
%   (ScanImage WG<->ALS limitation; see status.md s3.5 / handoff 2026-06-17.)
%
%   v4 bypasses the WG entirely and drives D3.2 with a low-level
%   dabs.vidrio.ddi.rdi.DoTask, which never touches scannerset/linePeriod
%   -> arms fine under ALS.
%
% MECHANISM:
%   - Finite DoTask on D3.2, internal sample clock R_HZ.
%   - Start trigger = /vDAQ0/D2.2 rising  (= D0.0 frame-clock T-split).
%     The task latches on the FIRST frame-clock edge (= ALS cycle 0), then
%     replays a buffer whose leading zeros encode N cycles of delay, so the
%     HIGH pulse lands at cycle N.
%   - Buffer: [ zeros(N*cycle_period*R) ; ones(pulse_width*R) ; tail ].
%
%   DETERMINISM PRECONDITION: arm() must complete BEFORE the first frame
%   clock edge. acqModeStart fires well ahead of head_pad (~2.2-3.5 s), so
%   there is margin; verify empirically by cycle agreement across >=3 runs.
%
% PREREQS (do ONCE, by hand, before the session):
%   1) Remove WG 'TrigLegato130-2' in Resource Config (frees D3.2).
%   2) Wiring unchanged: D3.2->T->AI7(+Legato+D2.1); D0.0->T->AI6 + D2.2.
%   3) Run sync_v4_probe.m once to confirm hDAQ accessor + output path.
%
% REGISTER: acqModeStart -> syncArmStart ; acqAbort+acqDone -> syncDisarm.
%   frameAcquired stays EMPTY (per-frame UF overflows at imaging rates).
%
% TUNING: edit syncParams() below, OR override at runtime without editing
%   this file:   setappdata(0,'sync_v4_params', struct('N',800,'R_Hz',1e5,...))
% =========================================================================
    APPKEY = 'sync_v4_task';
    try
        p = syncParams();

        % --- clean up any stale task from a prior run (re-construct each run) ---
        old = getappdata(0, APPKEY);
        if ~isempty(old) && isvalid(old)
            try, old.abort(); catch, end
            try, delete(old);  catch, end
        end
        setappdata(0, APPKEY, []);

        % --- obtain hDAQ -----------------------------------------------------
        hDAQ = i_getVdaq(p.daq_name);

        % --- build the pulse buffer ------------------------------------------
        lead = round(p.N * p.cycle_period_s * p.R_Hz);   % delay to cycle N
        high = round(p.pulse_width_s * p.R_Hz);          % HIGH width
        tail = round(p.tail_s * p.R_Hz);                 % return-to-low margin
        pulseVec = [zeros(lead,1); ones(high,1); zeros(tail,1)];
        nSamp = numel(pulseVec);

        % --- construct + arm the DoTask --------------------------------------
        hT = dabs.vidrio.ddi.rdi.DoTask.createDoTask(hDAQ, 'injTrig');
        hT.addChannel(p.do_chan);
        hT.cfgSampClkTiming(p.R_Hz, 'finite', nSamp);
        hT.cfgDigEdgeStartTrig(p.trigger_term, 'rising');   % = D2.2 frame clock
        hT.writeOutputBuffer(pulseVec);
        hT.start();                                          % arm: waits for D2.2

        % --- persist handle + the params actually used (for QC / align) ------
        setappdata(0, APPKEY, hT);
        setappdata(0, 'sync_v4_armed', struct( ...
            'N', p.N, 'R_Hz', p.R_Hz, 'cycle_period_s', p.cycle_period_s, ...
            'pulse_width_s', p.pulse_width_s, 'nSamp', nSamp, ...
            'trigger_term', p.trigger_term, 'do_chan', p.do_chan, ...
            't_arm', datestr(now,'yyyy-mm-dd HH:MM:SS')));

        fprintf(['[sync] armed DoTask on %s, trig %s rising, ' ...
                 'target cycle N=%d (R=%.0f Hz, nSamp=%d, ~%.3fs delay)\n'], ...
                 p.do_chan, p.trigger_term, p.N, p.R_Hz, nSamp, lead/p.R_Hz);
    catch ME
        fprintf(2, '[sync] DoTask ARM FAILED: %s\n', ME.message);
        if ~isempty(ME.stack)
            fprintf(2, '       at %s line %d\n', ME.stack(1).name, ME.stack(1).line);
        end
    end
end

% =========================================================================
function p = syncParams()
% Defaults. Override at runtime via setappdata(0,'sync_v4_params', struct(...)).
    p = struct( ...
        'daq_name',       'vDAQ0',          ...
        'do_chan',        'D3.2',           ...
        'trigger_term',   '/vDAQ0/D2.2',    ...  % frame-clock T-split (rising)
        'cycle_period_s', 8.0e-3,           ...  % 125 Hz, 4-line (confirmed 2026-06-17)
        'N',              500,              ...  % target ALS cycle
        'R_Hz',           1e5,              ...  % DoTask sample clock (modest)
        'pulse_width_s',  0.15,             ...  % ~0.1-0.2 s
        'tail_s',         0.05);                 % return-to-low margin
    ov = getappdata(0, 'sync_v4_params');
    if ~isempty(ov) && isstruct(ov)
        f = fieldnames(ov);
        for k = 1:numel(f), p.(f{k}) = ov.(f{k}); end
    end
end

% =========================================================================
function hDAQ = i_getVdaq(name)
    rs = dabs.resources.ResourceStore();
    hDAQ = [];
    % strategy A: by name
    try
        r = rs.filterByName(name);
        if iscell(r), if ~isempty(r), hDAQ = r{1}; end
        elseif ~isempty(r), hDAQ = r; end
    catch, end
    % strategy B: borrow hDAQ from a WaveformGenerator if one still exists
    if isempty(hDAQ)
        try
            wgs = rs.filterByClass('dabs.generic.WaveformGenerator');
            if ~isempty(wgs), hDAQ = wgs{1}.hDAQ; end
        catch, end
    end
    assert(~isempty(hDAQ), ...
        '[sync] vDAQ "%s" not found; run sync_v4_probe to confirm the accessor.', name);
end
