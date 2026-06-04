function syncDisarm(~, ~)
% ScanImage 'acqAbort' / 'acqDone' user function.
% Cancel all pending sync timers and force every configured WG line LOW (safety),
% so an aborted acquisition can never leave a trigger line stuck high.
    delete(timerfindall('Tag','syncTrig'));
    names = {};
    try
        if evalin('base','exist(''syncTriggers'',''var'')')
            cfg = evalin('base','syncTriggers');
            names = unique({cfg.wg});
        end
    catch
    end
    for i = 1:numel(names)
        try
            hWG = dabs.resources.ResourceStore().filterByName(names{i});
            if iscell(hWG), hWG = hWG{1}; end
            if ~isempty(hWG), hWG.writeLineToVal(0); end
        catch
        end
    end
    disp('[sync] disarmed; configured lines set low')
end
