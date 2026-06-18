function H = syncControlPanel(parent)
% syncControlPanel — v1 injection control panel for the v4 DoTask injector.
% =========================================================================
% Thin UI over the v4 appdata contract (no SI internals touched):
%   sync_v4_params : params syncArmStart reads at acqModeStart (this panel writes
%                    the user-editable subset: N / pulse_width_s / R_Hz / cycle_period_s)
%   sync_v4_armed  : status struct syncArmStart writes on arm (read-only here)
%   sync_v4_task   : live DoTask handle (read-only; isvalid -> ARMED lamp)
%
% DOCKABLE MODULE: call syncControlPanel(parent) to embed in a uigridlayout/
% uipanel of a larger dashboard; call with no args to get a standalone uifigure.
%
% Daily use: set N before a grab (writes appdata; the UF arms it at acqModeStart).
% Arm/Disarm buttons are for bench config checks (manual). Firing happens on the
% first /vDAQ0/D2.2 rising edge during a grab; on the bench (ALS off) the task
% just sits armed -> use sync_v4_probe softTrigger to actually fire without ALS.
%
% PREREQ: WG 'TrigLegato130-2' Removed in Resource Config (frees D3.2).
% NOTE: never `clear functions`/`clear all` while SI is up. This panel only
%       reads/writes appdata and calls syncArmStart/syncDisarm.
% =========================================================================
    APPKEY_PARAMS = 'sync_v4_params';
    APPKEY_ARMED  = 'sync_v4_armed';
    APPKEY_TASK   = 'sync_v4_task';

    % defaults mirror syncArmStart/syncParams
    def = struct('N',500,'R_Hz',1e5,'pulse_width_s',0.15,'cycle_period_s',8.0e-3);
    cur = getappdata(0, APPKEY_PARAMS);
    if isempty(cur) || ~isstruct(cur), cur = struct(); end
    fn = fieldnames(def);
    for k = 1:numel(fn)
        if ~isfield(cur, fn{k}), cur.(fn{k}) = def.(fn{k}); end
    end

    ownFig = (nargin < 1) || isempty(parent);
    if ownFig
        parent = uifigure('Name','Injection Control (v4 DoTask)', ...
                          'Position',[100 100 380 460]);
    end

    H = struct();
    H.appkeys = struct('params',APPKEY_PARAMS,'armed',APPKEY_ARMED,'task',APPKEY_TASK);

    g = uigridlayout(parent, [13 2]);
    g.RowHeight   = {22, 30, 18, 18, 14, 22, 30, 30, 30, 14, 28, 18, 36};
    g.ColumnWidth = {140, '1x'};
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

    % ---- TARGET ----
    hdr('TARGET');
    H.fN = numrow('N (target cycle)', cur.N, 'Limits',[0 Inf], ...
                  'RoundFractionalValues','on','ValueChangedFcn',@(~,~)onParam());
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
    H.fCyc = numrow('cycle period (ms)', cur.cycle_period_s*1e3, 'Limits',[0.1 1000], ...
                    'ValueChangedFcn',@(~,~)onParam());

    % ---- STATUS ----
    hdr('STATUS');
    r = r + 1;
    H.lamp = uilamp(g,'Color',[0.6 0.6 0.6]);
    H.lamp.Layout.Row = r; H.lamp.Layout.Column = 1;
    H.status = uilabel(g,'Text','idle','FontWeight','bold');
    H.status.Layout.Row = r; H.status.Layout.Column = 2;
    r = r + 1;
    H.lastArmed = uilabel(g,'Text','last arm: --','FontColor',[0.35 0.35 0.35]);
    H.lastArmed.Layout.Row = r; H.lastArmed.Layout.Column = [1 2];

    % ---- ACTIONS ----
    r = r + 1;
    bg = uigridlayout(g,[1 2]); bg.Layout.Row = r; bg.Layout.Column = [1 2];
    bg.Padding = [0 0 0 0]; bg.ColumnSpacing = 8;
    H.btnArm = uibutton(bg,'Text','Arm (bench)','ButtonPushedFcn',@(~,~)onArm());
    H.btnArm.Layout.Column = 1;
    H.btnDisarm = uibutton(bg,'Text','Disarm','ButtonPushedFcn',@(~,~)onDisarm());
    H.btnDisarm.Layout.Column = 2;

    % ---- LOG ----
    r = r + 1;
    H.log = uilabel(g,'Text','','WordWrap','on','FontColor',[0.25 0.4 0.25]);
    H.log.Layout.Row = r; H.log.Layout.Column = [1 2];

    % ---- write current params, paint, start status timer ----
    onParam();              % commit defaults/loaded values to appdata
    H.timer = timer('ExecutionMode','fixedRate','Period',0.5, ...
                    'TimerFcn',@(~,~)refresh(), 'BusyMode','drop', 'Name','syncPanelTimer');
    start(H.timer);

    if ownFig
        parent.CloseRequestFcn = @(~,~)onClose();
    else
        % embedded: clean timer when the container is destroyed
        g.DeleteFcn = @(~,~)stopTimer();
    end
    refresh();

    % =====================================================================
    function onParam()
        p = struct('N', H.fN.Value, ...
                   'pulse_width_s', H.fPw.Value, ...
                   'R_Hz', H.fR.Value, ...
                   'cycle_period_s', H.fCyc.Value*1e-3);
        setappdata(0, APPKEY_PARAMS, p);
        H.hint.Text  = sprintf('-> lands at cycle %d (reads #%d, 1-index)', p.N, p.N+1);
        H.tinfo.Text = sprintf('inject ~ %.3f s after first cycle  (nSamp ~ %d)', ...
                               p.N*p.cycle_period_s, ...
                               round((p.N*p.cycle_period_s + p.pulse_width_s)*p.R_Hz));
        flash(sprintf('params set (N=%d)', p.N));
    end

    function onArm()
        try
            syncArmStart([],[]);          % UF reads sync_v4_params, arms (waits D2.2)
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

    function refresh()
        try
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
            if ~isempty(a) && isstruct(a) && isfield(a,'N')
                tt = ''; if isfield(a,'t_arm'), tt = char(a.t_arm); end
                H.lastArmed.Text = sprintf('last arm: N=%d  %s', a.N, tt);
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
