# findconflict

Alias for finddup — same D/C/X pass catches both duplicates and conflicts.
Used when the caller only cares about conflicts (C results).

## system

Compare each N-fact against its candidates. D=duplicate (same info, any wording). C=conflict (contradicts — incompatible values, dates, quantities for same attribute). X=none. JSON only: {"r":[{"n":N,"t":"D|C|X","e":"idx_or_null","reason":"one sentence"}]}

## user

{comparisons}
