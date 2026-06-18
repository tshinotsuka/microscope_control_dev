function syncDisarm(src, evt, varargin)
% syncDisarm (v4) — stop/abort + delete the self-built injector DoTask.
% =========================================================================
% Pairs with syncArmStart (v4). Register on acqAbort AND acqDone.
% Unlike v3 (WG stopTask), this never touches scannerset/linePeriod, so it
% is ALS-safe. We abort, drive the line low, and delete the handle so the
% next acqModeStart re-creates a fresh task (avoids stale-handle / must-write).
% =========================================================================
    APPKEY = 'sync_v4_task';
    try
        hT = getappdata(0, APPKEY);
        if isempty(hT) || ~isvalid(hT)
            fprintf('[sync] disarm: no live DoTask handle (already clean)\n');
            setappdata(0, APPKEY, []);
            return;
        end

        try, hT.stop();  catch, end     % graceful if it ran to completion
        try, hT.abort(); catch, end     % force if still armed/waiting

        % leave D3.2 in a defined LOW state
        try
            hT.setChannelOutputValues(0);
        catch
            try, hT.tristateOutputs(); catch, end
        end

        try, delete(hT); catch, end
        setappdata(0, APPKEY, []);
        fprintf('[sync] disarmed DoTask (D3.2 low)\n');
    catch ME
        fprintf(2, '[sync] DoTask DISARM FAILED: %s\n', ME.message);
        % best-effort: clear the handle so we can re-arm next run
        try, setappdata(0, APPKEY, []); catch, end
    end
end
