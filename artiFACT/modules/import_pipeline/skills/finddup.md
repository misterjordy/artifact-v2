# finddup

Compare new facts against existing candidates. D=duplicate, C=conflict, X=neither.

## system

Compare each N-fact against its candidates. D=duplicate (same info, any wording). C=conflict (contradicts). X=none. Aggressive: abbreviations, rewordings, unit changes = D. Different values for same attribute = C. Numbers matter: "71 artifacts" vs "78 artifacts" = C. JSON only: {"r":[{"n":N,"t":"D|C|X","e":"idx_or_null","reason":"one sentence"}]}

## user

{comparisons}
