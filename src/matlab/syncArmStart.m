function syncArmStart(src, evt, varargin)
% syncArmStart (v2) — fixed-frame injection arm
% ------------------------------------------------------------------------
% acqModeStart User Function. Arms the injector Waveform Generator so it
% waits for the D2.2 frame-clock trigger and fires a single finite pulse at
% the configured Start delay (= N x cycle_period -> cycle N).
%
% Why a UF (not the widget): during ALS the WG widget Start/Stop are locked
% (the acquisition owns the vDAQ), and a pre-arm done before enabling ALS is
% torn down when ALS turns on. The only place left to arm is from inside the
% acquisition lifecycle = here.
%
% ALS-safe: this does NOT call linePeriod (which is undefined for the ALS
% StimulusField and was the source of the old throw). It only computes the
% WG buffer and starts the task -- the exact pair the widget Start performs.
%
% Pairing: register on acqModeStart. Pair with syncDisarm on acqAbort+acqDone.
% Do NOT put anything on frameAcquired (per-frame UF overflows >~17 Hz).
% ------------------------------------------------------------------------
    try
        wgs = dabs.resources.ResourceStore().filterByClass('dabs.generic.WaveformGenerator');
        assert(~isempty(wgs), '[sync] no WaveformGenerator resource found');
        wg = wgs{1};                      % single WG ('TrigLegato130-2')

        try, wg.stopTask(); catch, end    % clean slate (ok if not running)

        wg.computeWaveform();             % (re)generate output buffer  <-- must-write-buffer fix
        % If computeWaveform alone is not enough and startTask still reports
        % "Must write digital data to output buffer", uncomment ONE of:
        %   wg.updateWaveform();
        %   wg.updateTask();

        wg.startTask();                   % ARM: waits for /vDAQ0/D2.2 (rising)

        fprintf('[sync] armed WG ''%s'' (finite, waiting D2.2 frame clock)\n', wg.name);
    catch ME
        % Surface the exact failure so we know if ALS resource ownership
        % blocks startTask (vDAQ busy) vs a buffer/reserve issue.
        fprintf(2, '[sync] WG ARM FAILED: %s\n', ME.message);
    end
end
