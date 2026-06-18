function syncDisarm(src, evt, varargin)
% syncDisarm (v4) — stop/abort + drive D3.2 low + delete the injector DoTask.
% =========================================================================
% Pairs with syncArmStart (v4). Register on acqAbort AND acqDone.
% ALS-safe (never touches scannerset/linePeriod). Re-creating the task each
% acqModeStart avoids stale handles, so here we fully tear it down.
% =========================================================================
    APPKEY = 'sync_v4_task';
    try
        hT = getappdata(0, APPKEY);
        if isempty(hT) || ~isvalid(hT)
            setappdata(0, APPKEY, []);
            fprintf('[sync] disarm: no live DoTask (already clean)\n');
            return;
        end

        try, hT.stop();  catch, end     % graceful if it already completed
        try, hT.abort(); catch, end     % force if still armed/waiting

        % leave the line in a defined LOW state
        try
            hT.setChannelOutputValues(0);
        catch
            try, hT.tristateOutputs(); catch, end
        end

        try, delete(hT); catch, end
        setappdata(0, APPKEY, []);
        fprintf('[sync] disarmed DoTask (line LOW)\n');
    catch ME
        fprintf(2, '[sync] DoTask DISARM FAILED: %s\n', ME.message);
        try, setappdata(0, APPKEY, []); catch, end
    end
end
