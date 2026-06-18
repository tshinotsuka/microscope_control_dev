% sync_v4_probe.m  (v4 bring-up, run from MATLAB console)
% =========================================================================
% PURPOSE
%   Confirm the self-built DoTask path BEFORE rewriting the User Functions.
%   This is the DoTask analogue of the WG "Test B" (finite, NO start trigger
%   -> expect ONE clean edge on AI7). It nails down every v4 unknown:
%     (1) how to obtain hDAQ (the vDAQ resource)
%     (2) D3.2 is actually free after WG 'TrigLegato130-2' is Removed
%     (3) createDoTask / addChannel / cfgSampClkTiming / writeOutputBuffer /
%         start / softTrigger / stop signatures behave as captured
%     (4) the D3.2 -> T -> AI7 output path fires (record a grab, run diag_ttl)
%
% PRECONDITIONS (do these first, by hand)
%   - ALS scan mode selected but acquisition OFF (no grab running).
%   - WG 'TrigLegato130-2' REMOVED in Resource Configuration (frees D3.2).
%       Confirm D3.2 reserverInfo is no longer "<Reserved: TrigLegato130-2>".
%   - Wiring unchanged: D3.2 -> T -> AI7 (+ Legato + D2.1 aux).
%   - This probe uses softTrigger (NO D2.2). It only proves the OUTPUT path
%     and the API. The real "arm-during-ALS" + D2.2 test happens in the UF.
%
% SAFETY
%   - Do NOT run `clear functions` / `clear all` while SI is up (unloads MDF).
%   - This script aborts/deletes its own task at the end (and on error).
% =========================================================================

% ---- editable probe params -------------------------------------------------
DAQ_NAME   = 'vDAQ0';     % vDAQ resource name (confirm in STEP 1 output)
DO_CHAN    = 'D3.2';      % injector DO line
R_HZ       = 1e5;         % DoTask sample clock (modest: 10 us resolution)
PULSE_S    = 0.15;        % HIGH width (~0.1-0.2 s)
LEAD_S     = 0.20;        % short lead before the pulse (probe only; no trigger)
TAIL_S     = 0.05;        % return-to-low margin
% ---------------------------------------------------------------------------

hT = [];
cleanupObj = onCleanup(@() i_cleanup(hT));

try
    fprintf('\n==== sync_v4_probe ====\n');

    % ---- STEP 1: obtain hDAQ ------------------------------------------------
    % Print what ResourceStore knows so the accessor is unambiguous.
    rs = dabs.resources.ResourceStore();
    fprintf('[1] locating vDAQ "%s" ...\n', DAQ_NAME);

    hDAQ = [];
    % strategy A: by name (most robust if available)
    try
        r = rs.filterByName(DAQ_NAME);
        if iscell(r), if ~isempty(r), hDAQ = r{1}; end
        elseif ~isempty(r), hDAQ = r; end
    catch ME1
        fprintf('    filterByName not usable (%s)\n', ME1.message);
    end
    % strategy B: borrow from a still-present WaveformGenerator (if not removed yet)
    if isempty(hDAQ)
        try
            wgs = rs.filterByClass('dabs.generic.WaveformGenerator');
            if ~isempty(wgs)
                hDAQ = wgs{1}.hDAQ;
                fprintf('    (got hDAQ via a WaveformGenerator that still exists)\n');
            end
        catch, end
    end
    assert(~isempty(hDAQ), ['could not find vDAQ. Inspect rs and set DAQ_NAME. ' ...
        'Try: rs  /  whos  /  rs.filterByClass(''dabs.resources.Resource'')']);
    fprintf('    hDAQ = %s (class %s)\n', i_nameof(hDAQ), class(hDAQ));

    % ---- STEP 2: report D3.2 reservation state ------------------------------
    % If you still see "<Reserved: TrigLegato130-2>" here, the WG was NOT
    % removed -> remove it in Resource Config, then re-run.
    try
        fprintf('[2] hDAQ.hDOs = %s\n', mat2str(size(hDAQ.hDOs)));
        for k = 1:numel(hDAQ.hDOs)
            d = hDAQ.hDOs(k);
            fprintf('    hDOs(%d): %s  reserver=%s\n', k, i_nameof(d), i_reserver(d));
        end
    catch ME2
        fprintf('    (could not enumerate hDOs: %s)\n', ME2.message);
    end

    % ---- STEP 3: build the DoTask (NO start trigger; softTrigger) -----------
    lead = round(LEAD_S  * R_HZ);
    high = round(PULSE_S * R_HZ);
    tail = round(TAIL_S  * R_HZ);
    pulseVec = [zeros(lead,1); ones(high,1); zeros(tail,1)];
    nSamp = numel(pulseVec);
    fprintf('[3] building DoTask: R=%.0f Hz, nSamp=%d (~%.3f s)\n', R_HZ, nSamp, nSamp/R_HZ);

    hT = dabs.vidrio.ddi.rdi.DoTask.createDoTask(hDAQ, 'injProbe');
    hT.addChannel(DO_CHAN);
    hT.cfgSampClkTiming(R_HZ, 'finite', nSamp);
    % NOTE: probe uses softTrigger, so DO NOT call cfgDigEdgeStartTrig here.
    hT.writeOutputBuffer(pulseVec);     % if this errors on shape, try logical()/transpose

    % ---- STEP 4: fire it ----------------------------------------------------
    % Start the (now armed-on-soft) task, then software-trigger one playback.
    fprintf('[4] start + softTrigger -> expect ONE rising edge on AI7\n');
    hT.start();
    try
        hT.softTrigger();
    catch
        % some builds auto-run on start() when no hardware trigger is set
        fprintf('    (softTrigger not needed / not present; task may auto-run)\n');
    end
    try, hT.waitUntilTaskDone(5); catch, pause(nSamp/R_HZ + 0.3); end

    fprintf('[OK] probe fired without error.\n');
    fprintf(['     -> Take a short Data Recorder grab around a re-fire to capture AI7,\n' ...
             '        then run diag_ttl.py on AI7 (expect edges@2.5V = 1).\n']);
    fprintf('     To re-fire for the grab: hT.start(); hT.softTrigger();\n');
    fprintf('     (handle left alive as base var hT_probe for manual re-fire)\n');
    assignin('base', 'hT_probe', hT);
    hT = [];   % hand ownership to base var; skip auto-cleanup of this handle

catch ME
    fprintf(2, '[PROBE FAILED] %s\n', ME.message);
    fprintf(2, '  at %s line %d\n', ME.stack(1).name, ME.stack(1).line);
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
    s = '?';
    try, s = h.name; catch
        try, s = char(h.name); catch, end
    end
end

function s = i_reserver(d)
    s = '(unreserved)';
    try
        ri = d.reserverInfo;
        if ~isempty(ri), s = char(string(ri)); end
    catch
        try, s = char(string(d.reserver)); catch, end
    end
end
