function syncArmStart(src, evt, varargin)
% syncArmStart (v3) — ALS-safe arm: startTask ONLY (no computeWaveform).
% ------------------------------------------------------------------------
% ROOT CAUSE (2026-06-17 stack trace):
%   WaveformGenerator.computeWaveform -> refreshWvfmParams (line 357)
%     -> hSI.hScan2D.scannerset.linePeriod(ss)
%       -> GalvoGalvo.linePeriod (line 489) asserts the scanfield is an
%          ImagingField -> FAILS for the ALS StimulusField.
%   => computeWaveform CANNOT run while ALS is the active scan mode.
%      (This is a ScanImage WG<->ALS limitation, not our logic.)
%
% PREREQS (do ONCE, with ALS OFF, before the run):
%   1) wg.computeWaveform();      % pre-write the output buffer (works only ALS-off)
%   2) WG widget: Show Widget OFF % else stop/startTask's notify('redrawWidget')
%                                 %   re-triggers computeWaveform -> linePeriod
%
% Register on acqModeStart. Pair with syncDisarm on acqAbort+acqDone.
% frameAcquired stays EMPTY.
% ------------------------------------------------------------------------
    try
        wgs = dabs.resources.ResourceStore().filterByClass('dabs.generic.WaveformGenerator');
        assert(~isempty(wgs), '[sync] no WaveformGenerator resource found');
        wg = wgs{1};

        try, wg.stopTask(); catch, end   % clean slate (no redraw if widget hidden)
        wg.startTask();                  % start with the PRE-COMPUTED buffer (no recompute)

        fprintf('[sync] armed WG ''%s'' (startTask, waiting D2.2)\n', wg.name);
    catch ME
        fprintf(2, '[sync] WG ARM FAILED: %s\n', ME.message);
    end
end
