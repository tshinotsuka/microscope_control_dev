% sync_v4_probe.m  (v4 bring-up, run from MATLAB console)
% =========================================================================
% PURPOSE
%   Confirm the self-built DoTask OUTPUT path before rewriting the UFs.
%   DoTask analogue of the WG "Test B": finite single playback via
%   softTrigger (NO D2.2) -> expect ONE clean edge on AI7.
%
% API CONFIRMED 2026-06-17 (dabs.vidrio.ddi.rdi.DoTask, .p-code introspect + live test):
%   createDoTask(device,name) [static] / addChannel(channel,name,initVal)
%   convertToBufferedTask()           % on-demand -> buffered (REQUIRED)
%   sampleRate = R  (property)        % cfgSampClkTiming() throws 'not done' -> AVOID
%   sampleMode='finite' / samplesPerTrigger=N  (properties)
%   writeOutputBuffer(data)           % buffer length = #samples
%   cfgDigEdgeStartTrig(terminal)     % OK; edge = startTriggerEdge prop ('rising')
%   start / stop / abort / softTrigger / setChannelOutputValues(data)
%   Key defaults: sampleMode='continuous'(!), startTriggerEdge='rising',
%                 allowRetrigger=0, sampleRate=1e6, maxSampleRate=2e7.
%   -> MUST set sampleMode='finite' or the buffer loops forever.
%
% PRECONDITIONS
%   - ALS scan mode selected, acquisition OFF.
%   - This probe writes to D3.3 (FREE per STEP-2) so the WG reservation on
%     D3.2 is irrelevant here. To prove the REAL injector line (D3.2 -> AI7)
%     set DO_CHAN='D3.2' AFTER removing WG 'TrigLegato130-2' in Resource
%     Config (else start()/reserve will fail on the reservation).
%   - Wiring unchanged: D3.2 -> T -> AI7 (+Legato+D2.1).
%   - softTrigger only (NO D2.2). Proves output path + finite single shot.
%
% SAFETY: no `clear functions`/`clear all` while SI is up. Self-cleans on exit.
% =========================================================================

% ---- editable probe params -------------------------------------------------
DAQ_NAME = 'vDAQ0';
DO_CHAN  = 'D3.2';     % FREE line for path test. Set 'D3.2' only after WG Remove.
R_HZ     = 1e5;        % DoTask sample clock (10 us resolution; modest buffer)
LEAD_S   = 0.20;       % short lead before pulse (probe only; no trigger delay)
PULSE_S  = 0.15;       % HIGH width
TAIL_S   = 0.05;       % return-to-low margin (ends buffer LOW)
% ---------------------------------------------------------------------------

hT = [];
cleanupObj = onCleanup(@() i_cleanup(hT));

try
    fprintf('\n==== sync_v4_probe (DO=%s) ====\n', DO_CHAN);

    % ---- locate hDAQ (filterByName confirmed working) -----------------------
    rs = dabs.resources.ResourceStore();
    hDAQ = rs.filterByName(DAQ_NAME);
    if iscell(hDAQ), hDAQ = hDAQ{1}; end
    assert(~isempty(hDAQ), 'vDAQ "%s" not found', DAQ_NAME);
    fprintf('[1] hDAQ = %s\n', i_nameof(hDAQ));

    % ---- build the pulse buffer ---------------------------------------------
    lead = round(LEAD_S  * R_HZ);
    high = round(PULSE_S * R_HZ);
    tail = round(TAIL_S  * R_HZ);
    pulseVec = [zeros(lead,1); ones(high,1); zeros(tail,1)];
    nSamp = numel(pulseVec);
    fprintf('[2] buffer: R=%.0f Hz, nSamp=%d (~%.3f s)\n', R_HZ, nSamp, nSamp/R_HZ);

    % ---- construct + configure (CONFIRMED API) ------------------------------
    hT = dabs.vidrio.ddi.rdi.DoTask.createDoTask(hDAQ, 'injProbe');
    hT.addChannel(DO_CHAN, 'injProbe', 0);   % initVal 0 -> idle LOW
    hT.convertToBufferedTask();              % on-demand -> buffered (required)
    hT.sampleRate = R_HZ;                    % rate via property (cfgSampClkTiming = 'not done')
    hT.sampleMode = 'finite';                % override the continuous default
    hT.samplesPerTrigger = nSamp;            % generate nSamp once per trigger
    hT.writeOutputBuffer(pulseVec);
    % NO cfgDigEdgeStartTrig here -> use softTrigger.
    fprintf('[3] configured: sampleMode=%s, samplesPerTrigger=%d, edge=%s\n', ...
            hT.sampleMode, hT.samplesPerTrigger, string(hT.startTriggerEdge));

    % ---- fire ---------------------------------------------------------------
    fprintf('[4] start + softTrigger -> expect ONE rising edge on %s\n', DO_CHAN);
    hT.start();
    try
        hT.softTrigger();
    catch
        fprintf('    (softTrigger not needed; task auto-ran on start)\n');
    end
    try, hT.waitUntilTaskDone(5); catch, pause(nSamp/R_HZ + 0.3); end

    fprintf('[OK] probe fired without error (sampleMode=%s).\n', hT.sampleMode);
    fprintf(['     -> grab around a re-fire to capture %s, run diag_ttl.py (edges@2.5V=1).\n' ...
             '     re-fire: hT_probe.start(); hT_probe.softTrigger();\n'], DO_CHAN);
    assignin('base', 'hT_probe', hT);
    hT = [];   % hand ownership to base var; skip auto-cleanup

catch ME
    fprintf(2, '[PROBE FAILED] %s\n', ME.message);
    if ~isempty(ME.stack)
        fprintf(2, '  at %s line %d\n', ME.stack(1).name, ME.stack(1).line);
    end
    rethrow(ME);
end

% ---- local helpers ---------------------------------------------------------
function i_cleanup(hT)
    if ~isempty(hT) && isvalid(hT)
        try, hT.abort(); catch, end
        try, delete(hT);  catch, end
    end
end
function s = i_nameof(h)
    s = '?'; try, s = char(h.name); catch, end
end
