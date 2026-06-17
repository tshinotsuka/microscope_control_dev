function syncDisarm(src, evt, varargin)
% syncDisarm (v3) — stopTask only.
% REQUIRES WG widget Show Widget OFF, otherwise stopTask's
% notify('redrawWidget') -> widget.redraw -> computeWaveform -> linePeriod
% throws under ALS (StimulusField). See syncArmStart header for the chain.
    try
        wgs = dabs.resources.ResourceStore().filterByClass('dabs.generic.WaveformGenerator');
        assert(~isempty(wgs), '[sync] no WaveformGenerator resource found');
        wg = wgs{1};
        wg.stopTask();
        fprintf('[sync] disarmed WG ''%s''\n', wg.name);
    catch ME
        fprintf(2, '[sync] WG DISARM FAILED: %s\n', ME.message);
    end
end
