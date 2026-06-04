function syncControlPanel()
% GUI WIREFRAME (sync Phase 0) for the control/sync layer. Layout + minimal wiring.
% - Shows/edits the `syncTriggers` config consumed by syncArmStart (acqModeStart).
% - "Apply to base" writes the table to base `syncTriggers`; "Load from base" reads it.
% - Status line is a placeholder; live arm-state from ScanImage events is a later step.
% NOT yet integrated into ScanImage. Run `syncControlPanel` to view the layout.
% Design source of truth: docs/sync_architecture.md (s5 Phase 0).

    f = uifigure('Name','Sync Control (wireframe)','Position',[100 100 640 360]);
    g = uigridlayout(f,[4 1]);
    g.RowHeight = {'fit','1x','fit','fit'};

    % header
    lbl = uilabel(g,'Text', ...
        'vDAQ sync triggers   (vDAQ generates -> Aux records -> TIFF; see sync_architecture.md)', ...
        'FontWeight','bold');
    lbl.Layout.Row = 1;

    % trigger table (one row per modality; injector is the first entry)
    t = uitable(g, ...
        'ColumnName',   {'name','wg (device)','delaySec','pulseSec','enabled'}, ...
        'ColumnEditable',[true true true true true], ...
        'ColumnFormat', {'char','char','numeric','numeric','logical'}, ...
        'Data', { 'injector','Trig Legato130', 2, 0.2, true });
    t.Layout.Row = 2;

    % status line (create BEFORE buttons so callbacks can capture it)
    sl = uilabel(g,'Text', ...
        'status: edit the table, then "Apply to base". (live arm-state = later step)');
    sl.Layout.Row = 4;

    % buttons
    bg = uigridlayout(g,[1 4]); bg.Layout.Row = 3;
    uibutton(bg,'Text','Add row',        'ButtonPushedFcn',@(b,e) iAddRow(t));
    uibutton(bg,'Text','Remove last',    'ButtonPushedFcn',@(b,e) iDelRow(t));
    uibutton(bg,'Text','Load from base', 'ButtonPushedFcn',@(b,e) iLoad(t,sl));
    uibutton(bg,'Text','Apply to base',  'FontWeight','bold', ...
             'ButtonPushedFcn',@(b,e) iApply(t,sl));
end

% ---------- callbacks ----------
function iAddRow(t)
    t.Data = [t.Data; {'', '', 1, 0.2, true}];
end

function iDelRow(t)
    if size(t.Data,1) > 0, t.Data(end,:) = []; end
end

function iApply(t, sl)
    d = t.Data;
    s = struct('name',{},'wg',{},'delaySec',{},'pulseSec',{},'enabled',{});
    for i = 1:size(d,1)
        s(i).name     = d{i,1};
        s(i).wg       = d{i,2};
        s(i).delaySec = d{i,3};
        s(i).pulseSec = d{i,4};
        s(i).enabled  = logical(d{i,5});
    end
    assignin('base','syncTriggers',s);
    sl.Text = sprintf('status: applied %d trigger(s) to base `syncTriggers`.', numel(s));
end

function iLoad(t, sl)
    try
        s = evalin('base','syncTriggers');
        d = cell(numel(s),5);
        for i = 1:numel(s)
            d(i,:) = {s(i).name, s(i).wg, s(i).delaySec, s(i).pulseSec, logical(s(i).enabled)};
        end
        t.Data = d;
        sl.Text = sprintf('status: loaded %d trigger(s) from base.', numel(s));
    catch
        sl.Text = 'status: no `syncTriggers` in base yet.';
    end
end
