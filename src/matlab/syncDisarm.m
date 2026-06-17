function syncDisarm(src, evt, varargin)
% syncDisarm (v2) — fixed-frame injection disarm
% ------------------------------------------------------------------------
% acqAbort + acqDone User Function. Stops the injector WG task and drives
% the output line back to its default (low). Mirrors the widget Stop.
%
% Use this if your existing syncDisarm does not actually stopTask the WG.
% If your current disarm already prints "[sync] disarmed; configured lines
% set low" AND stops the WG task, you can keep it.
% ------------------------------------------------------------------------
    try
        wgs = dabs.resources.ResourceStore().filterByClass('dabs.generic.WaveformGenerator');
        assert(~isempty(wgs), '[sync] no WaveformGenerator resource found');
        wg = wgs{1};

        try, wg.stopTask(); catch, end
        try, wg.writeLineToDefaultVal(); catch, end   % drive D3.2 low

        fprintf('[sync] disarmed WG ''%s''; line low\n', wg.name);
    catch ME
        fprintf(2, '[sync] WG DISARM FAILED: %s\n', ME.message);
    end
end
