function legatoInjectStart(~, ~)
% ScanImage 'acqModeStart' user function -- runs ONCE per acquisition.
% Schedules a single injector pulse with NO per-frame callback:
%   wait delaySec -> writeLineToVal(1) -> after pulseSec -> writeLineToVal(0)
% The pulse is driven through the vDAQ-owned Waveform Generator "Trig Legato130"
% (writeLineToVal, confirmed working). The real edge is timestamped by the
% Aux Trigger loopback on D2.1, so offline alignment stays exact regardless of
% the small host-timer jitter on the delay.
%
% Because nothing runs on frameAcquired, this does not load the MATLAB frame
% queue -> no "Frame queue overflow" at any frame rate the imaging can sustain.
%
% Base workspace config (set before Grab):
%   delaySec   : baseline before injection, seconds.   (default 5)
%   pulseSec   : pulse width, seconds.                  (default 0.2)
%   targetFrame: OPTIONAL. If set and delaySec is NOT set, delaySec is computed
%                as targetFrame / scanFrameRate (read from hSI).

    hWG = iGetWG();
    if isempty(hWG)
        warning('[legato] WG "Trig Legato130" not found; injection NOT scheduled.');
        return
    end

    % --- resolve pulse width ---
    if evalin('base','exist(''pulseSec'',''var'')')
        pulseSec = evalin('base','pulseSec');
    else
        pulseSec = 0.2;
    end

    % --- resolve delay (seconds preferred; else frames/frameRate; else default) ---
    delaySec = [];
    if evalin('base','exist(''delaySec'',''var'')')
        delaySec = evalin('base','delaySec');
    elseif evalin('base','exist(''targetFrame'',''var'')')
        try
            fr = evalin('base','hSI.hRoiManager.scanFrameRate');
            tf = evalin('base','targetFrame');
            delaySec = tf / fr;
            fprintf('[legato] targetFrame=%d @ %.3f Hz -> delaySec=%.3f s\n', tf, fr, delaySec);
        catch
            warning('[legato] could not read scanFrameRate; set delaySec instead.');
        end
    end
    if isempty(delaySec)
        delaySec = 5;
    end

    % --- arm: clear stale timers, start low, schedule the single pulse ---
    delete(timerfindall('Tag','legatoInject'));
    try, hWG.writeLineToVal(0); catch, end

    t = timer('Tag','legatoInject', 'ExecutionMode','singleShot', ...
              'StartDelay', delaySec, ...
              'TimerFcn', @(tt,~) iFire(tt, hWG, pulseSec));
    start(t);
    fprintf('[legato] injection armed: fire in %.3f s, pulse %.3f s\n', delaySec, pulseSec);
end


function iFire(t, hWG, pulseSec)
    try
        hWG.writeLineToVal(1);
        fprintf('[legato] injector ON\n');
    catch ME
        warning('[legato] writeLineToVal(1): %s', ME.message);
    end
    stop(t); delete(t);
    % schedule the falling edge (also tagged, so cleanup catches it)
    t2 = timer('Tag','legatoInject', 'ExecutionMode','singleShot', ...
               'StartDelay', pulseSec, ...
               'TimerFcn', @(tt,~) iOff(tt, hWG));
    start(t2);
end


function iOff(t, hWG)
    try
        hWG.writeLineToVal(0);
        fprintf('[legato] injector OFF\n');
    catch ME
        warning('[legato] writeLineToVal(0): %s', ME.message);
    end
    stop(t); delete(t);
end


function hWG = iGetWG()
    hWG = [];
    try
        hRS = dabs.resources.ResourceStore();
        hWG = hRS.filterByName('Trig Legato130');
        if iscell(hWG), hWG = hWG{1}; end
    catch ME
        warning('[legato] resource store lookup failed: %s', ME.message);
    end
end
