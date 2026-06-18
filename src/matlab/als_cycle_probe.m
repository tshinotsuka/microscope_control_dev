% als_cycle_probe.m  (run from MATLAB console with ScanImage up + ALS configured)
% =========================================================================
% PURPOSE
%   Identify which LIVE hSI property exposes the ALS *cycle period* (one full
%   pass over all lines). Right now the cycle is hardcoded 8.0 ms / 125 Hz in
%   syncParams() (syncArmStart) and syncControlPanel -> silent-misconfig risk
%   the moment the ALS trajectory (line count / cycle time) changes. Once the
%   property path is known, both read it live via ONE helper.
%
% METHOD (no guessing):
%   With ALS dialed to a KNOWN cycle (e.g. 4-line, 8.0 ms = 125 Hz), scan the
%   numeric scalar properties of the relevant SI subsystems and FLAG any whose
%   value equals the known cycle (0.008 s) OR the known rate (125 Hz) within a
%   tolerance. The flagged name(s) ARE the candidate property path(s) to wire.
%   A focused context dump (period|rate|frame|line|cycle props) is also printed.
%
% IMPORTANT
%   - Do NOT wire scannerset.linePeriod: it asserts ImagingField under ALS
%     (the WG dead-end). We want a cycle/frame-period valid in ALS scan mode.
%   - 'linePeriod' is skipped here so its assert never fires while introspecting.
%
% SAFETY: read-only. No clear functions / clear all. Mutates nothing on hSI.
% =========================================================================

% ---- set to the ACTUAL configured ALS cycle before running -----------------
KNOWN_CYCLE_S = 8.0e-3;              % cycle period you have dialed in [s]
KNOWN_RATE_HZ = 1 / KNOWN_CYCLE_S;  % = 125 Hz
TOL_REL       = 0.02;               % +/- 2% match window
SKIP_PROPS    = {'linePeriod'};     % names not to read (avoid ALS asserts)
% ---------------------------------------------------------------------------

try
    hSI = i_getSI();
    fprintf('\n==== als_cycle_probe (target %.4f s / %.3f Hz) ====\n', ...
            KNOWN_CYCLE_S, KNOWN_RATE_HZ);
    fprintf('[ctx] scan mode: %s\n', i_scanMode(hSI));

    subs = i_subsystems(hSI);   % {name, handle}

    % ---- pass 1: value-match flagging -------------------------------------
    hits = cell(0,3);   % {path, value, kind}
    for i = 1:size(subs,1)
        nm = subs{i,1}; h = subs{i,2};
        if isempty(h) || ~i_ok(h), continue; end
        for pn = i_props(h)
            p = pn{1};
            if any(strcmpi(p, SKIP_PROPS)), continue; end
            v = i_tryget(h, p);
            if ~(isscalar(v) && isnumeric(v) && isfinite(v)), continue; end
            isCyc  = i_near(v, KNOWN_CYCLE_S, TOL_REL);
            isRate = i_near(v, KNOWN_RATE_HZ, TOL_REL);
            if isCyc || isRate
                kind = 'period[s]'; if isRate, kind = 'rate[Hz]'; end
                hits(end+1,:) = {sprintf('hSI.%s.%s',nm,p), v, kind}; %#ok<AGROW>
            end
        end
    end

    % ---- pass 2: focused context dump -------------------------------------
    fprintf('\n-- context (period|rate|frame|line|cycle props) --\n');
    for i = 1:size(subs,1)
        nm = subs{i,1}; h = subs{i,2};
        if isempty(h) || ~i_ok(h), continue; end
        for pn = i_props(h)
            p = pn{1};
            if any(strcmpi(p, SKIP_PROPS)), continue; end
            if isempty(regexpi(p, 'period|rate|frame|line|cycle', 'once')), continue; end
            v = i_tryget(h, p);
            if isscalar(v) && isnumeric(v) && isfinite(v)
                fprintf('   hSI.%s.%-30s = %g\n', nm, p, v);
            end
        end
    end

    % ---- verdict ----------------------------------------------------------
    fprintf('\n==== FLAGGED (== known cycle/rate within %.0f%%) ====\n', TOL_REL*100);
    if isempty(hits)
        fprintf(2, ['  none matched. Confirm ALS is the active mode + KNOWN_CYCLE_S is\n' ...
                    '  what is dialed in; widen TOL_REL; or add a subsystem in i_subsystems().\n']);
    else
        for i = 1:size(hits,1)
            fprintf('  %-42s = %-12g (%s)\n', hits{i,1}, hits{i,2}, hits{i,3});
        end
        fprintf(['\n  -> pick the [s] one (or 1/rate) and put it behind ONE helper\n' ...
                 '     i_alsCyclePeriodS(hSI) shared by syncArmStart + syncControlPanel.\n']);
    end

catch ME
    fprintf(2, '[probe failed] %s\n', ME.message);
    if ~isempty(ME.stack)
        fprintf(2, '  at %s line %d\n', ME.stack(1).name, ME.stack(1).line);
    end
    rethrow(ME);
end

% ---- helpers ---------------------------------------------------------------
function hSI = i_getSI()
    hSI = [];
    try, hSI = evalin('base','hSI'); catch, end
    assert(~isempty(hSI) && i_ok(hSI), 'hSI not found (is ScanImage running?)');
end

function tf = i_ok(h)
    tf = false; try, tf = isvalid(h); catch, end
end

function s = i_scanMode(hSI)
    s = '?';
    try, s = char(hSI.hScan2D.scanMode); catch, end
    if strcmp(s,'?'), try, s = class(hSI.hScan2D); catch, end; end
end

function subs = i_subsystems(hSI)
    cand = { ...
        'hRoiManager',   @() hSI.hRoiManager;   ...
        'hScan2D',       @() hSI.hScan2D;        ...
        'hStackManager', @() hSI.hStackManager;  ...
        'hFastZ',        @() hSI.hFastZ };
    subs = cell(0,2);
    for i = 1:size(cand,1)
        h = []; try, h = cand{i,2}(); catch, end
        subs(end+1,:) = {cand{i,1}, h}; %#ok<AGROW>
    end
end

function pr = i_props(h)
    pr = {}; try, pr = properties(h)'; catch, end   % row for for-loop
end

function v = i_tryget(h, pn)
    v = []; try, v = h.(pn); catch, end
end

function tf = i_near(v, target, relTol)
    tf = abs(v - target) <= relTol*abs(target);
end
