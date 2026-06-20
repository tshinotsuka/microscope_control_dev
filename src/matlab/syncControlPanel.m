function H = syncControlPanel(parent)
% syncControlPanel — v2 injection control panel for the v4 DoTask injector.
% =========================================================================
% Thin UI over the v4 appdata contract (no SI internals touched):
%   sync_v4_params : params syncArmStart reads at acqModeStart (this panel writes
%                    the user-editable subset: N / pulse_width_s / R_Hz / cycle_period_s)
%   sync_v4_armed  : status struct syncArmStart writes on arm (read-only here)
%   sync_v4_task   : live DoTask handle (read-only; isvalid -> ARMED lamp)
%
% v2 changes (usability — fixes "changed N but nothing changed"):
%   1. TARGET CYCLE is entered DIRECTLY (1-index, e.g. 501). The panel stores
%      N = target-1 in appdata, so the on-screen number == the cycle injection
%      actually lands on. (v1 exposed raw N with a "target cycle" label =
%      off-by-one trap: typing 5 injected at #6.)
%   2. STALE detector: if a task is ARMED and the field no longer matches the
%      armed N, a banner says so -- because changing the field only rewrites
%      appdata; the LIVE task keeps the old N until re-armed. This is the usual
%      reason a change "didn't take".
%   3. "Apply & Arm" : commit fields -> disarm (if armed) -> arm, in one click,
%      so the current target always takes effect.
%   4. "Test fire (bench)" : soft-trigger via sync_v4_probe to fire without ALS.
%   5. cycle period AUTO-TRACKS the scanner: the status timer re-reads
%      hRoiManager.scanFramePeriod (the alsCyclePeriodS path) every tick, so a
%      scan-rate change in ScanImage updates the (read-only) field + the N
%      timing estimate automatically. "Re-read cycle" forces it via
%      alsCyclePeriodS (with its warning) for an explicit refresh.
%
% DOCKABLE: syncControlPanel(parent) embeds in a uigridlayout/uipanel of a larger
% dashboard; no args -> standalone uifigure.
%
% PREREQ: WG 'TrigLegato130-2' Removed in Resource Config (frees D3.2).
% NOTE: never `clear functions`/`clear all` while SI is up. This panel only
%       reads/writes appdata and calls syncArmStart/syncDisarm/sync_v4_probe.
% =========================================================================
    APPKEY_PARAMS = 'sync_v4_params';
    APPKEY_ARMED  = 'sync_v4_armed';
    APPKEY_TASK   = 'sync_v4_task';

    % defaults mirror syncArmStart/syncParams; cycle period from LIVE hSI
    def = struct('N',500,'R_Hz',1e5,'pulse_width_s',0.15, ...
                 'cycle_period_s', alsCyclePeriodS([], 8.0e-3));
    cur = getappdata(0, APPKEY_PARAMS);
    if isempty(cur) || ~isstruct(cur), cur = struct(); end
    fn = fieldnames(def);
    for k = 1:numel(fn)
        if ~isfield(cur, fn{k}), cur.(fn{k}) = def.(fn{k}); end
    end
    cur.cycle_period_s = alsCyclePeriodS([], 8.0e-3);   % scanner-derived: open on live

    ownFig = (nargin < 1) || isempty(parent);
    if ownFig
        parent = uifigure('Name','Injection Control (v4 DoTask)', ...
                          'Position',[100 100 400 560]);
    end

    H = struct();
    H.appkeys = struct('params',APPKEY_PARAMS,'armed',APPKEY_ARMED,'task',APPKEY_TASK);

    g = uigridlayout(parent, [18 2]);
    g.RowHeight   = repmat({'fit'}, 1, 18);
    g.ColumnWidth = {150, '1x'};
    g.RowSpacing  = 6;  g.Padding = [10 10 10 10];

    r = 0;
    function lbl = hdr(txt)
        r = r + 1;
        lbl = uilabel(g,'Text',txt,'FontWeight','bold','FontColor',[0.2 0.2 0.45]);
        lbl.Layout.Row = r; lbl.Layout.Column = [1 2];
    end
    function fld = numrow(txt, val, varargin)
        r = r + 1;
        L = uilabel(g,'Text',txt); L.Layout.Row = r; L.Layout.Column = 1;
        fld = uieditfield(g,'numeric','Value',val,varargin{:});
        fld.Layout.Row = r; fld.Layout.Column = 2;
    end
    function b = btnrow(cols)
        r = r + 1;
        b = uigridlayout(g,[1 numel(cols)]);
        b.Layout.Row = r; b.Layout.Column = [1 2];
        b.Padding = [0 0 0 0]; b.ColumnSpacing = 8;
        b.ColumnWidth = cols;
    end

    % ---- TARGET ----
    hdr('TARGET');
    H.fTarget = numrow('inject at cycle # (1-index)', cur.N + 1, ...
                       'Limits',[1 Inf], 'RoundFractionalValues','on', ...
                       'ValueChangedFcn',@(~,~)onParam());
    r = r + 1;
    H.hint = uilabel(g,'Text','','FontColor',[0.35 0.35 0.35]);
    H.hint.Layout.Row = r; H.hint.Layout.Column = [1 2];
    r = r + 1;
    H.tinfo = uilabel(g,'Text','','FontColor',[0.35 0.35 0.35]);
    H.tinfo.Layout.Row = r; H.tinfo.Layout.Column = [1 2];

    % ---- PULSE / CLOCK ----
    hdr('PULSE / CLOCK');
    H.fPw = numrow('pulse width (s)', cur.pulse_width_s, 'Limits',[1e-3 5], ...
                   'ValueChangedFcn',@(~,~)onParam());
    H.fR  = numrow('R (Hz)', cur.R_Hz, 'Limits',[1e3 2e7], ...
                   'ValueChangedFcn',@(~,~)onParam());
    H.fCyc = numrow('cycle period (ms) [auto/hSI]', cur.cycle_period_s*1e3, ...
                    'Editable','off', 'Limits',[0.1 1000]);   % scanner-derived, auto-tracked
    bC = btnrow({'1x'});
    H.btnReread = uibutton(bC,'Text','Re-read cycle from hSI (force)', ...
                           'ButtonPushedFcn',@(~,~)onReread());
    H.btnReread.Layout.Column = 1;

    % ---- STATUS ----
    hdr('STATUS');
    r = r + 1;
    sg = uigridlayout(g,[1 2]); sg.Layout.Row = r; sg.Layout.Column = [1 2];
    sg.Padding = [0 0 0 0]; sg.ColumnWidth = {26,'1x'};
    H.lamp = uilamp(sg,'Color',[0.6 0.6 0.6]); H.lamp.Layout.Column = 1;
    H.status = uilabel(sg,'Text','idle','FontWeight','bold'); H.status.Layout.Column = 2;
    r = r + 1;
    H.stale = uilabel(g,'Text','','FontWeight','bold','FontColor',[0.75 0.45 0]);
    H.stale.Layout.Row = r; H.stale.Layout.Column = [1 2];
    r = r + 1;
    H.lastArmed = uilabel(g,'Text','last arm: --','FontColor',[0.35 0.35 0.35]);
    H.lastArmed.Layout.Row = r; H.lastArmed.Layout.Column = [1 2];

    % ---- ACTIONS ----
    bA = btnrow({'1x','1x'});
    H.btnApplyArm = uibutton(bA,'Text','Apply & Arm', ...
                             'BackgroundColor',[0.82 0.92 0.82], ...
                             'ButtonPushedFcn',@(~,~)onApplyArm());
    H.btnApplyArm.Layout.Column = 1;
    H.btnDisarm = uibutton(bA,'Text','Disarm','ButtonPushedFcn',@(~,~)onDisarm());
    H.btnDisarm.Layout.Column = 2;
    bB = btnrow({'1x','1x'});
    H.btnArm = uibutton(bB,'Text','Arm only (bench)','ButtonPushedFcn',@(~,~)onArm());
    H.btnArm.Layout.Column = 1;
    H.btnTest = uibutton(bB,'Text','Test fire (bench)','ButtonPushedFcn',@(~,~)onTestFire());
    H.btnTest.Layout.Column = 2;

    % ---- LOG ----
    r = r + 1;
    H.log = uilabel(g,'Text','','WordWrap','on','FontColor',[0.25 0.4 0.25]);
    H.log.Layout.Row = r; H.log.Layout.Column = [1 2];

    % ---- write current params, paint, start status timer ----
    onParam();
    H.timer = timer('ExecutionMode','fixedRate','Period',0.5, ...
                    'TimerFcn',@(~,~)refresh(), 'BusyMode','drop', 'Name','syncPanelTimer');
    start(H.timer);

    if ownFig
        parent.CloseRequestFcn = @(~,~)onClose();
    else
        g.DeleteFcn = @(~,~)stopTimer();
    end
    refresh();

    % =====================================================================
    function p = curParams()
        N = max(0, round(H.fTarget.Value) - 1);     % target (1-index) -> N
        p = struct('N', N, ...
                   'pulse_width_s', H.fPw.Value, ...
                   'R_Hz', H.fR.Value, ...
                   'cycle_period_s', H.fCyc.Value*1e-3);
    end

    function p = commitParams()
        % write appdata + update derived labels; NO log flash (auto-track-safe)
        p = curParams();
        setappdata(0, APPKEY_PARAMS, p);
        H.hint.Text  = sprintf('N = %d  (= target-1; injects at cycle #%d)', p.N, p.N+1);
        H.tinfo.Text = sprintf('inject ~%.3f s after first cycle  (nSamp ~%d)', ...
                               p.N*p.cycle_period_s, ...
                               round((p.N*p.cycle_period_s + p.pulse_width_s)*p.R_Hz));
    end

    function onParam()
        p = commitParams();
        flash(sprintf('params set (target #%d, N=%d)', p.N+1, p.N));
    end

    function onReread()
        try
            T = alsCyclePeriodS([], H.fCyc.Value*1e-3);
            H.fCyc.Value = T*1e3;
            onParam();
            flash(sprintf('cycle re-read from hSI: %.3f ms', T*1e3));
        catch ME
            flash(['REREAD ERR: ' ME.message]);
        end
    end

    function onApplyArm()
        onParam();                       % commit fields first
        try
            hT = getappdata(0, APPKEY_TASK);
            if ~isempty(hT) && isvalid(hT), syncDisarm([],[]); end
            syncArmStart([],[]);          % UF reads sync_v4_params, arms (waits D2.2)
            flash('applied + armed (current target now live)');
        catch ME
            flash(['APPLY ERR: ' ME.message]);
        end
        refresh();
    end

    function onArm()
        try
            syncArmStart([],[]);
            flash('Arm issued (see [sync] console; lamp -> armed if start OK)');
        catch ME
            flash(['ARM ERR: ' ME.message]);
        end
        refresh();
    end

    function onDisarm()
        try
            syncDisarm([],[]);
            flash('Disarm issued');
        catch ME
            flash(['DISARM ERR: ' ME.message]);
        end
        refresh();
    end

    function onTestFire()
        % bench soft-trigger (ALS off): fire the armed pulse once without a D2.2
        % edge. Exact call matches sync_v4_probe's API; guarded so a mismatch
        % only logs.
        try
            sync_v4_probe('softTrigger');
            flash('soft trigger sent (bench fire)');
        catch ME
            flash(['TESTFIRE ERR (check sync_v4_probe API): ' ME.message]);
        end
    end

    function refresh()
        try
            % auto-track scanner cycle period (the alsCyclePeriodS path:
            % hRoiManager.scanFramePeriod). Quiet inline read so a not-up SI or
            % unconfigured ALS does NOT spam warnings every tick; on a valid
            % change we update the (read-only) field + re-commit appdata so a
            % scan-rate change in ScanImage flows into N's timing estimate.
            try
                T = evalin('base','hSI').hRoiManager.scanFramePeriod;
                if isscalar(T) && isnumeric(T) && isfinite(T) && T > 0 ...
                        && abs(T*1e3 - H.fCyc.Value) > 1e-3
                    H.fCyc.Value = T*1e3;
                    commitParams();
                end
            catch
                % SI not up / ALS not configured: keep last cycle, stay quiet
            end

            hT = getappdata(0, APPKEY_TASK);
            armed = ~isempty(hT) && isvalid(hT);
            if armed
                H.lamp.Color = [0.2 0.75 0.2];
                H.status.Text = 'ARMED  (waiting /vDAQ0/D2.2)';
            else
                H.lamp.Color = [0.6 0.6 0.6];
                H.status.Text = 'idle';
            end
            a = getappdata(0, APPKEY_ARMED);
            curN = max(0, round(H.fTarget.Value) - 1);
            if ~isempty(a) && isstruct(a) && isfield(a,'N')
                tt = ''; if isfield(a,'t_arm'), tt = char(a.t_arm); end
                H.lastArmed.Text = sprintf('last arm: N=%d (#%d)  %s', a.N, a.N+1, tt);
                if armed && a.N ~= curN
                    H.stale.Text = sprintf(['STALE: armed N=%d (#%d) != field #%d ' ...
                        '-> press Apply & Arm'], a.N, a.N+1, curN+1);
                else
                    H.stale.Text = '';
                end
            else
                H.lastArmed.Text = 'last arm: --';
                H.stale.Text = '';
            end
        catch
            % never let the timer throw
        end
    end

    function flash(msg)
        H.log.Text = msg;
    end

    function stopTimer()
        try, if isfield(H,'timer') && isvalid(H.timer), stop(H.timer); delete(H.timer); end; catch, end
    end

    function onClose()
        stopTimer();
        delete(parent);
    end
end
