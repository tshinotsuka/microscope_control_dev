function legatoInjectStop(~, ~)
% ScanImage 'acqAbort' / 'acqDone' user function.
% Cancels any pending injector timers and forces the line LOW (safety),
% so an aborted acquisition can never leave the injector line stuck high.
    delete(timerfindall('Tag','legatoInject'));
    try
        hRS = dabs.resources.ResourceStore();
        hWG = hRS.filterByName('Trig Legato130');
        if iscell(hWG), hWG = hWG{1}; end
        if ~isempty(hWG), hWG.writeLineToVal(0); end
    catch
    end
    disp('[legato] injection timers cleared; line set low')
end
