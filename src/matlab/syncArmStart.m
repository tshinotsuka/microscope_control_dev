function syncArmStart(~, ~)
% ScanImage 'acqModeStart' user function -- runs ONCE per acquisition.
% Generic, config-driven arm: schedule a single pulse for each ENABLED trigger.
% No per-frame callback (see sync_architecture.md s4). Each pulse is driven on a
% vDAQ-owned Waveform Generator line via writeLineToVal; the real edge is
% timestamped by an Aux Trigger loopback (-> TIFF), so offline alignment is exact.
% This generalizes legatoInjectStart.m: the injector is now one config entry.
%
% Config = base workspace struct array `syncTriggers` with fields:
%   name        : label (char)                       e.g. 'injector'
%   wg          : Waveform Generator device name     e.g. 'Trig Legato130'
%   delaySec    : delay from acq start, seconds       (optional)
%   targetFrame : OPTIONAL alt; delaySec = targetFrame / scanFrameRate
%   pulseSec    : pulse width, seconds                (default 0.2)
%   enabled     : logical                             (default true)
%
% Example (set before Grab):
%   syncTriggers = struct('name','injector','wg','Trig Legato130', ...
%                         'delaySec',2,'pulseSec',0.2,'enabled',true);
%   % add more entries later (opto, etc.) -> struct array.

    cfg = iGetConfig();
    if isempty(cfg), return; end          % nothing configured -> no-op

    delete(timerfindall('Tag','syncTrig'));   % clear stale timers

    for k = 1:numel(cfg)
        c = cfg(k);
        if ~iField(c,'enabled',true), continue; end
        wgName = iField(c,'wg','');
        hWG = iGetWG(wgName);
        if isempty(hWG)
            warning('[sync] WG "%s" not found; "%s" NOT armed.', wgName, iField(c,'name','?'));
            continue
        end
        try, hWG.writeLineToVal(0); catch, end
        delaySec = iResolveDelay(c);
        pulseSec = iField(c,'pulseSec',0.2);
        nm       = iField(c,'name','trigger');
        t = timer('Tag','syncTrig','ExecutionMode','singleShot','StartDelay',delaySec, ...
                  'TimerFcn', @(tt,~) iFire(tt, hWG, pulseSec, nm));
        start(t);
        fprintf('[sync] armed "%s": fire in %.3f s, pulse %.3f s\n', nm, delaySec, pulseSec);
    end
end

% ---------- helpers ----------
function cfg = iGetConfig()
    cfg = [];
    try
        if evalin('base','exist(''syncTriggers'',''var'')')
            cfg = evalin('base','syncTriggers');
        end
    catch ME
        warning('[sync] reading syncTriggers failed: %s', ME.message);
    end
end

function v = iField(s, f, default)
    if isstruct(s) && isfield(s,f) && ~isempty(s.(f))
        v = s.(f);
    else
        v = default;
    end
end

function delaySec = iResolveDelay(c)
    delaySec = iField(c,'delaySec',[]);
    if isempty(delaySec)
        tf = iField(c,'targetFrame',[]);
        if ~isempty(tf)
            try
                fr = evalin('base','hSI.hRoiManager.scanFrameRate');
                delaySec = tf / fr;
                fprintf('[sync] "%s": targetFrame=%g @ %.3f Hz -> %.3f s\n', ...
                        iField(c,'name','?'), tf, fr, delaySec);
            catch
                warning('[sync] "%s": could not read scanFrameRate; set delaySec.', iField(c,'name','?'));
            end
        end
    end
    if isempty(delaySec), delaySec = 5; end
end

function hWG = iGetWG(name)
    hWG = [];
    if isempty(name), return; end
    try
        hWG = dabs.resources.ResourceStore().filterByName(name);
        if iscell(hWG), hWG = hWG{1}; end
    catch ME
        warning('[sync] resource store lookup failed: %s', ME.message);
    end
end

function iFire(t, hWG, pulseSec, nm)
    try
        hWG.writeLineToVal(1);
        fprintf('[sync] "%s" ON\n', nm);
    catch ME
        warning('[sync] "%s" writeLineToVal(1): %s', nm, ME.message);
    end
    stop(t); delete(t);
    t2 = timer('Tag','syncTrig','ExecutionMode','singleShot','StartDelay',pulseSec, ...
               'TimerFcn', @(tt,~) iOff(tt, hWG, nm));
    start(t2);
end

function iOff(t, hWG, nm)
    try
        hWG.writeLineToVal(0);
        fprintf('[sync] "%s" OFF\n', nm);
    catch ME
        warning('[sync] "%s" writeLineToVal(0): %s', nm, ME.message);
    end
    stop(t); delete(t);
end
