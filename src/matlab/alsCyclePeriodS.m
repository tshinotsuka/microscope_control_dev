function T = alsCyclePeriodS(hSI, fallback_s)
% alsCyclePeriodS — live ALS cycle period [s] from hSI, with explicit fallback.
% =========================================================================
% SINGLE SOURCE for syncArmStart (syncParams) + syncControlPanel, replacing the
% hardcoded 8.0 ms cycle. Property confirmed by als_cycle_probe.m (2026-06-19):
%   hSI.hRoiManager.scanFramePeriod  (in ALS each logged frame = one cycle,
%   so scanFramePeriod = the full-cycle period; NOT scannerset.linePeriod,
%   which asserts ImagingField under ALS).
%
% Usage:
%   T = alsCyclePeriodS();            % live hSI from base, fallback 8 ms
%   T = alsCyclePeriodS(hSI);         % pass a handle, fallback 8 ms
%   T = alsCyclePeriodS(hSI, 6.0e-3); % custom fallback
%
% NOT silent: warns to console if the live read fails and the fallback is used.
% =========================================================================
    if nargin < 2 || isempty(fallback_s), fallback_s = 8.0e-3; end
    if nargin < 1 || isempty(hSI)
        try, hSI = evalin('base','hSI'); catch, hSI = []; end
    end

    T = [];
    try, T = hSI.hRoiManager.scanFramePeriod; catch, end

    if ~(isscalar(T) && isnumeric(T) && isfinite(T) && T > 0)
        warning('[sync] ALS cycle period auto-read failed; using fallback %.4f s', fallback_s);
        T = fallback_s;
    end
end
