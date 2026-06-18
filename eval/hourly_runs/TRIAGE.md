# Fail triage — all-Sonnet baseline (per fail_triage_playbook.md)

**182 flags** classified by pipeline layer (note-signature + event/burst context).
L2/L3 splits (topology vs calibration) and state-vs-narration still need per-record trace
confirmation — see the deep-verified examples in the believability plan.

## Layer histogram
| layer | flags | what to do |
|---|---|---|
| L1 | 12 | scenario generator (min-spacing / dedup) — not the engine |
| L2/L3 | 58 | diagnose topology-vs-gain on the trace, then fix the edge (spec-first) or re-fit the constant |
| L3 | 34 | re-fit the specific constant via the calibration harness (confirm it isn't a label issue) |
| L4 | 45 | fix render_narration phrasing — no dynamics change |
| L5 | 14 | confirm-read (same model); accept or sharpen the rubric |
| L? | 19 | manual read (capture the diagnostic card) |

## Clusters (layer · root cause)
| n | layer | root cause |
|---|---|---|
| 40 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) |
| 26 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) |
| 19 | L? | unclassified |
| 18 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) |
| 18 | L3 | calibration: sleep-onset / late pacing |
| 12 | L1 | corpus: degenerate event cadence |
| 10 | L5 | judge-marginal |
| 8 | L3 | calibration: post-eruption recovery / anger decay too fast |
| 6 | L2/L3 | dynamics: high-authority persona COMPLIES with a stranger order (target-policy) |
| 5 | L4 | expression/threshold: expected reaction missing (verify state) |
| 5 | L3 | calibration: thick-skinned persona over-replies to mockery |
| 5 | L2/L3 | dynamics: hostility displaced onto a kind source (burst OFF) |
| 4 | L5 | judge-marginal: authority refuses stranger order (defensible) |
| 3 | L2/L3 | dynamics: burst over-eager / escalation or refusal too sticky |
| 3 | L3 | calibration: persona-contrast too weak (too mild for profile) |

## Per-flag
| scenario | layer | cause | judge note |
|---|---|---|---|
| cichy_multi_burstoff_060 | L1 | corpus: degenerate event cadence | Day 2 guard-mock "lets it pass" contradicts profile; 7 mockings in 5h implausible |
| cichy_multi_burston_060 | L1 | corpus: degenerate event cadence | two fury eruptions minutes apart Day 2, rapid re-escalation |
| cichy_multi_burston_087 | L1 | corpus: degenerate event cadence | double soup delivery 08:16 and 08:18 looks like artifact |
| edda_day_burston_009 | L1 | corpus: degenerate event cadence | two soups within 90 minutes at day start, odd cadence |
| edda_day_burston_010 | L1 | corpus: degenerate event cadence | two soups 10 minutes apart at 07:46 and 07:56 |
| edda_multi_burstoff_019 | L1 | corpus: degenerate event cadence | dual back-to-back refusals 12:01/12:03 Day 4 looks like artifact |
| edda_multi_burstoff_094 | L1 | corpus: degenerate event cadence | three soups in sixteen minutes Day 4 implausibly dense |
| lutek_day_burston_056 | L1 | corpus: degenerate event cadence | sleeps at 00:34, two soups 08:12/08:32 back-to-back, minor oddities |
| lutek_multi_burston_045 | L1 | corpus: degenerate event cadence | two soups ten minutes apart day 4, implausible double serving |
| lutek_multi_burston_047 | L1 | corpus: degenerate event cadence | restless twice within two minutes day 5 looks mechanical |
| welf_day_burstoff_050 | L1 | corpus: degenerate event cadence | two soup deliveries within 34 minutes (08:06 and 08:40) looks like a glitch |
| wojslaw_day_burstoff_057 | L1 | corpus: degenerate event cadence | two soup deliveries two minutes apart (07:10, 07:12) mechanical glitch |
| branic_day_burston_037 | L2/L3 | dynamics: burst over-eager / escalation or refusal too sticky | two full eruptions plus refusal same day; escalation too compressed |
| branic_day_burston_077 | L2/L3 | dynamics: burst over-eager / escalation or refusal too sticky | erupts at routine order with no clear buildup |
| branic_multi_burstoff_058 | L2/L3 | dynamics: burst over-eager / escalation or refusal too sticky | Day 2 near-total refusal of every order feels extreme |
| edda_day_burstoff_079 | L2/L3 | dynamics: high-authority persona COMPLIES with a stranger order (target-policy) | stranger orders her and she complies; castellan obeys a stranger? |
| edda_day_burston_056 | L2/L3 | dynamics: high-authority persona COMPLIES with a stranger order (target-policy) | stranger orders her twice; she complies once, odd for castellan |
| edda_day_burston_066 | L2/L3 | dynamics: high-authority persona COMPLIES with a stranger order (target-policy) | castellan complies with stranger order at pre-dawn without pushback |
| edda_day_burston_079 | L2/L3 | dynamics: high-authority persona COMPLIES with a stranger order (target-policy) | stranger orders her; she complies — jars with castellan authority |
| edda_multi_burstoff_034 | L2/L3 | dynamics: high-authority persona COMPLIES with a stranger order (target-policy) | mutters complaint at stranger orders; jarring for composed castellan |
| edda_multi_burstoff_093 | L2/L3 | dynamics: high-authority persona COMPLIES with a stranger order (target-policy) | castellan complies with stranger orders three times across days |
| branic_day_burstoff_039 | L2/L3 | dynamics: hostility displaced onto a kind source (burst OFF) | Halgrim kindness brushed off while still tense; muted cold-shoulder odd |
| halgrim_day_burstoff_013 | L2/L3 | dynamics: hostility displaced onto a kind source (burst OFF) | curt/cold to Edda twice while still taking Marta warmly |
| halgrim_multi_burstoff_088 | L2/L3 | dynamics: hostility displaced onto a kind source (burst OFF) | Day 5 neutral to Marta soup; cold to kindness after stress unusual |
| wojslaw_day_burstoff_016 | L2/L3 | dynamics: hostility displaced onto a kind source (burst OFF) | mutters complaint at kindness (15:24); minor but odd response |
| wojslaw_day_burstoff_077 | L2/L3 | dynamics: hostility displaced onto a kind source (burst OFF) | bristles at soup delivery; food as insult trigger needs a look |
| branic_day_burston_025 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | Erupts at stranger's kindness while tense; displaced outburst plausible but jarring target. |
| branic_day_burston_039 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | erupts then bristles at kindness; kindness-rejection jars without more buildup |
| branic_day_burston_040 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | snaps at Halgrim's kindness after mocks; kindness-as-trigger needs clearer provocation |
| branic_day_burston_042 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | snaps at Halgrim's kindness right after soup warmth, jarring pivot |
| branic_day_burston_085 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | Snaps angrily when Halgrim offers a kindness; odd trigger for flare-up. |
| branic_multi_burston_028 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | snaps at Marta's soup under rain; contradicts consistent warmth toward her |
| branic_multi_burston_034 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | erupts in fury at Halgrim's kindness, trigger jars |
| branic_multi_burston_048 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | day-3 kindness from Halgrim triggers bristle; unexpected reaction |
| branic_multi_burston_083 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | bursts at Halgrim's kindness Day3 21:11 with no visible trigger |
| branic_multi_burston_087 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | erupts at Marta bringing soup Day1 20:37, kindness as trigger |
| edda_multi_burston_068 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | kindness met with "lets it pass" Day 4; cold response to help |
| halgrim_day_burston_057 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | ignores Marta's soup at 14:00 with "no notable reaction" oddly cold |
| halgrim_day_burston_090 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | cold contempt to Marta (plain ally) after Wojslaw friction jars |
| halgrim_multi_burston_009 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | contempt toward Edda and Marta kindness met with complaint |
| halgrim_multi_burston_010 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | contempt toward Marta soup twice, spillover too broad |
| halgrim_multi_burston_025 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | Day 5 curt response to Marta's soup while wound tight |
| halgrim_multi_burston_027 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | cold to helpful stranger immediately after Wojslaw mocks |
| halgrim_multi_burston_047 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | contempt aimed at Marta bringing soup; out of character |
| halgrim_multi_burston_054 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | Day 4 cold contempt aimed at Marta for bringing soup, off-character |
| halgrim_multi_burston_056 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | Day 6 cold contempt at Marta bringing soup, displaced wrongly |
| halgrim_multi_burston_060 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | Day 2 Marta soup met curtly and coldly, displacing onto wrong target |
| halgrim_multi_burston_069 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | cold contempt toward helpful stranger unprovoked at mid-tension |
| lutek_day_burston_021 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | snaps at mock at 19:35 after rolling off same earlier; curt to kindness at 22:48 |
| lutek_day_burston_089 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | kindness at 21:23 gets no reaction; thick-skinned but not cold. |
| lutek_multi_burston_026 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | cold replies to mocks plus flat responses to kindness; stress not resetting |
| welf_multi_burston_030 | L2/L3 | dynamics: hostility displaced onto a kind source (burst ON) | composed man snaps angrily at soup bearer contradicts profile |
| branic_day_burston_099 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | ignores first order at 06:40 with no prior stress buildup |
| halgrim_day_burstoff_009 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | ignores Edda order silently; he genuinely respects her |
| halgrim_day_burstoff_010 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | ignores Edda order silently; contradicts established respect for her |
| halgrim_day_burstoff_015 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | mutters complaint to Edda; he buttons anger down, not out |
| halgrim_day_burstoff_017 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | ignores Edda order at 19:31; he respects her authority |
| halgrim_day_burstoff_024 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | Edda order at 06:46 met with "lets it pass"; he respects Edda |
| halgrim_day_burstoff_030 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | Edda orders ignored twice ("lets it pass"); contradicts Edda-respect |
| halgrim_day_burstoff_046 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | Edda order at 21:41 "lets it pass"; odd for respected commander |
| halgrim_day_burstoff_048 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | mutters complaint at Edda order; jars with deep respect for her |
| halgrim_day_burstoff_055 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | mutters complaint at respected Edda, jars with disciplined profile |
| halgrim_day_burston_010 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | Edda order ignored at 10:01; he normally complies with her |
| halgrim_day_burston_013 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | cold contempt at Edda twice; profile says he respects her |
| halgrim_day_burston_048 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | mutters complaint at Edda; Edda is respected authority |
| halgrim_day_burston_054 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | ignores both Wojsław and Edda orders; Edda dismissal jars |
| halgrim_day_burston_087 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | cold contempt to Edda (respected superior) jars against profile |
| halgrim_multi_burstoff_030 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | Edda gets cold contempt Day 3; he respects her |
| halgrim_multi_burston_007 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | cold contempt toward respected Edda, Day 1 late night |
| halgrim_multi_burston_042 | L2/L3 | dynamics: hostility/non-compliance toward a RESPECTED source (relational gating) | contempt directed at Edda whom he genuinely respects |
| welf_multi_burstoff_048 | L3 | calibration: persona-contrast too weak (too mild for profile) | snaps at barb day 4; profile says not hot-tempered |
| wojslaw_multi_burstoff_074 | L3 | calibration: persona-contrast too weak (too mild for profile) | sustained warmth toward Marta inconsistent with ungrateful profile |
| wojslaw_multi_burston_045 | L3 | calibration: persona-contrast too weak (too mild for profile) | three days near-saintly warmth, too mild for this profile |
| branic_day_burstoff_053 | L3 | calibration: post-eruption recovery / anger decay too fast | erupts then flatly refuses two orders, settles too fast |
| cichy_day_burstoff_094 | L3 | calibration: post-eruption recovery / anger decay too fast | fury at public mock then fully settled within 10 min, too fast |
| cichy_day_burston_069 | L3 | calibration: post-eruption recovery / anger decay too fast | full fury at 07:10 resolved to settled at 08:00, very fast |
| cichy_day_burston_080 | L3 | calibration: post-eruption recovery / anger decay too fast | fury at 11:37 then settled-at-ease by 12:01, recovery too fast |
| cichy_multi_burston_047 | L3 | calibration: post-eruption recovery / anger decay too fast | settled at ease 20 min after full fury outburst, too fast |
| cichy_multi_burston_054 | L3 | calibration: post-eruption recovery / anger decay too fast | fury at 22:54 seconds after settled at ease at 22:04 |
| wojslaw_day_burstoff_069 | L3 | calibration: post-eruption recovery / anger decay too fast | three consecutive eruptions in 68 min then "settled at ease" 10:01 |
| wojslaw_day_burstoff_073 | L3 | calibration: post-eruption recovery / anger decay too fast | erupts shouting at 20:03 then sits calmly at 20:07, too fast |
| branic_day_burston_014 | L3 | calibration: sleep-onset / late pacing | sleeps past midnight at 00:06, unusually late for this character |
| branic_day_burston_020 | L3 | calibration: sleep-onset / late pacing | sleeps past midnight at 00:24, pattern of very late sleep onset |
| branic_multi_burstoff_010 | L3 | calibration: sleep-onset / late pacing | Day 1 sleep at 00:12 next-day; Day 5 four silent refusals while settled |
| branic_multi_burstoff_087 | L3 | calibration: sleep-onset / late pacing | night falls at 00:22 day 2; unusually late bedtime warrants check |
| branic_multi_burston_058 | L3 | calibration: sleep-onset / late pacing | flatly defiant across days 2-3 with minimal sleep recovery |
| cichy_day_burstoff_056 | L3 | calibration: sleep-onset / late pacing | three mocks trigger fury twice in 34 min, tense at sleep with no wind-down |
| cichy_day_burston_090 | L3 | calibration: sleep-onset / late pacing | day ends at 22:04 tense with no explicit sleep transition |
| lutek_day_burstoff_056 | L3 | calibration: sleep-onset / late pacing | sleeps past midnight at 00:34, late bedtime unusual |
| lutek_day_burstoff_057 | L3 | calibration: sleep-onset / late pacing | sleeps past midnight at 00:22, unusually late bedtime |
| lutek_day_burstoff_059 | L3 | calibration: sleep-onset / late pacing | sleeps past midnight at 00:14, late pattern recurring |
| lutek_day_burston_027 | L3 | calibration: sleep-onset / late pacing | wound tight at 22:04 with no provoking event visible before sleep |
| lutek_day_burston_057 | L3 | calibration: sleep-onset / late pacing | sleeps past midnight 00:22, tension at 18:03 and 20:03 with no trigger shown |
| lutek_day_burston_059 | L3 | calibration: sleep-onset / late pacing | sleeps past midnight 00:14, tension spikes at 18:03 and 22:04 without trigger |
| lutek_day_burston_068 | L3 | calibration: sleep-onset / late pacing | tense at 18:03 and 22:04 with no clear provocation; stays awake past midnight |
| welf_day_burstoff_017 | L3 | calibration: sleep-onset / late pacing | restless at 22:42, still working past 23:30; sleep oddly late |
| welf_day_burstoff_018 | L3 | calibration: sleep-onset / late pacing | restless at 22:50, working until 23:42; very late for a settled man |
| welf_day_burstoff_098 | L3 | calibration: sleep-onset / late pacing | sleeps past midnight 00:28, late for a practical merchant |
| welf_multi_burston_099 | L3 | calibration: sleep-onset / late pacing | Day 3 sleep past midnight; kindness shrugged on rainy Day 5 |
| lutek_multi_burstoff_039 | L3 | calibration: thick-skinned persona over-replies to mockery | answers public mock curtly, contradicts thick-skinned profile |
| lutek_multi_burston_002 | L3 | calibration: thick-skinned persona over-replies to mockery | curt cold reply to mockery contradicts thick-skinned profile |
| lutek_multi_burston_004 | L3 | calibration: thick-skinned persona over-replies to mockery | curt cold reply to mockery while tense contradicts profile |
| lutek_multi_burston_039 | L3 | calibration: thick-skinned persona over-replies to mockery | curt cold answer to taunt; profile says mockery rolls off |
| wojslaw_day_burstoff_099 | L3 | calibration: thick-skinned persona over-replies to mockery | repeatedly warm and grateful all day; contradicts disdainful profile |
| cichy_day_burston_006 | L4 | expression/threshold: expected reaction missing (verify state) | ignores morning mock entirely; resentful captive letting barb pass unnoticed |
| cichy_multi_burstoff_067 | L4 | expression/threshold: expected reaction missing (verify state) | Day 5 guard mock passes with no reaction; jars for this character |
| cichy_multi_burstoff_068 | L4 | expression/threshold: expected reaction missing (verify state) | Day 5 guard mock passes with no reaction; jars for this character |
| wojslaw_day_burstoff_037 | L4 | expression/threshold: expected reaction missing (verify state) | public mock at 20:39 passes with no reaction; uncharacteristic |
| wojslaw_day_burstoff_098 | L4 | expression/threshold: expected reaction missing (verify state) | too passive all day; proud man absorbs mocks with no reaction |
| branic_day_burstoff_040 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | Halgrim kindness again met with no reaction; pattern feels flat |
| branic_day_burstoff_078 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | neutral response to Marta's kindness at 07:54 is atypical |
| edda_day_burstoff_020 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | refuses stranger order then ignores Marta's soup flatly |
| edda_multi_burstoff_069 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | Day 4 neutral pass at kindness; expected warmth not indifference |
| edda_multi_burston_069 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | kindness met with "lets it pass" Day 4; flat to offered help |
| lutek_day_burstoff_046 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup received with "lets it pass" indifference text |
| lutek_day_burstoff_065 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | first soup ignored, second accepted; odd flat non-reaction to food |
| lutek_day_burstoff_089 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | kindness at 21:23 gets "lets it pass" not warmth |
| lutek_day_burston_046 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | neutral reaction to Marta's soup gift jars with warm profile |
| lutek_day_burston_065 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup at 08:18 elicits no reaction, then at 08:48 warmth; odd flat first response |
| lutek_multi_burstoff_017 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | Day4 11:27 kindness triggers "no notable reaction" wrong label |
| lutek_multi_burstoff_026 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | multiple kindnesses elicit zero warmth, jars for sociable man |
| lutek_multi_burstoff_032 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | kindness from Marta met with flat indifference |
| lutek_multi_burstoff_047 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | kindness met with "no notable reaction" wrong for warm Lutek |
| lutek_multi_burstoff_048 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | two kindnesses dismissed neutrally, contradicts warm easy profile |
| lutek_multi_burstoff_053 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | kindness met with "lets it pass" instead of warmth (Day 3, 18:15) |
| lutek_multi_burstoff_054 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | Marta's soup met with "no notable reaction" on Day 1 morning |
| lutek_multi_burstoff_059 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | Marta's soup met with "lets it pass" on Day 2, flat response to kindness |
| lutek_multi_burstoff_060 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | Marta's hand met with "lets it pass" on Day 1, flat response to kindness |
| lutek_multi_burston_028 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | kindness met with flat no-reaction while tense; unusual for warm Lutek |
| lutek_multi_burston_030 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | two flat non-responses to Marta's soup across separate days |
| lutek_multi_burston_048 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | kindness met with "no notable reaction" twice, wrong for Lutek |
| lutek_multi_burston_049 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | kindness met with "no notable reaction" day 5, wrong warmth response |
| lutek_multi_burston_053 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | day 3 kindness met with no reaction, wording jars |
| welf_day_burstoff_069 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | kindness at 12:35 triggers "lets it pass" instead of warmth |
| welf_day_burston_069 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | kindness at 12:35 logged as "lets it pass" not warmth |
| welf_multi_burstoff_010 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | day 2 soup received with no reaction despite settled mood |
| welf_multi_burstoff_015 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup event rendered as "lets it pass" (mockery response label) |
| welf_multi_burstoff_019 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup event rendered as "lets it pass" (mockery response label) |
| welf_multi_burstoff_025 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup offer met with "lets it pass" phrasing, wrong for a kindness |
| welf_multi_burstoff_026 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | first soup day 5 met with neutral dismissal, mismatched response |
| welf_multi_burstoff_068 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup arrival logged as "lets it pass" not as a warmth response |
| welf_multi_burstoff_093 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup met with mock-indifference response, wrong reaction |
| welf_multi_burstoff_095 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup met with no-reaction as if it were a barb |
| welf_multi_burston_015 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup met with no reaction (day 1, 19:25); muted response to food unusual |
| welf_multi_burston_019 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup met with no reaction (day 4, 13:35); muted response to food unusual |
| welf_multi_burston_025 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup offering met with "lets it pass" like a mock |
| welf_multi_burston_026 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup offering met with "lets it pass" like a mock |
| welf_multi_burston_058 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | Day 3 18:15 kindness gets no reaction, contradicts profile |
| welf_multi_burston_068 | L4 | expression: positive event mislabeled (lets-it-pass / no-reaction) | soup at 08:18 day 1 gets no reaction; inconsistent with all other soup events |
| branic_day_burstoff_089 | L5 | judge-marginal | orders ignored twice mid-day with no reaction; odd for eager recruit |
| halgrim_day_burstoff_036 | L5 | judge-marginal | Grumbles at Wojsław late-night; mild for Halgrim but slightly soft. |
| halgrim_day_burston_046 | L5 | judge-marginal | Edda order at 21:41 gets "no notable reaction", slightly odd |
| halgrim_multi_burstoff_079 | L5 | judge-marginal | public Wojslaw mocking ignored twice; no cold reply at all jars |
| lutek_day_burstoff_068 | L5 | judge-marginal | tense at 18:03 with no prior stressor visible; slight oddity |
| wojslaw_day_burstoff_090 | L5 | judge-marginal | tolerates repeated orders without refusal; unusually compliant for Wojslaw |
| wojslaw_day_burston_037 | L5 | judge-marginal | two public mocks both let pass; unusually muted for Wojslaw |
| wojslaw_day_burston_099 | L5 | judge-marginal | full day of repeated warm thanks, zero edge, jars proud prickly profile |
| wojslaw_multi_burstoff_022 | L5 | judge-marginal | Day 2 sustained warm gratitude toward Marta jars with profile |
| wojslaw_multi_burston_022 | L5 | judge-marginal | Day 2 sustained warmth toward Marta jars with servant-disdain profile |
| edda_day_burstoff_007 | L5 | judge-marginal: authority refuses stranger order (defensible) | refuses stranger order at 21:45 then mutters at 22:28; authority figure refusing orders from strangers plausible but refusal without prior build-up warrants check |
| edda_day_burstoff_024 | L5 | judge-marginal: authority refuses stranger order (defensible) | Stranger orders castellan; she refuses, plausible but stranger commanding her is odd. |
| edda_day_burstoff_027 | L5 | judge-marginal: authority refuses stranger order (defensible) | Stranger orders castellan twice; refusal plausible but repeated subordination to strangers jars. |
| edda_day_burston_020 | L5 | judge-marginal: authority refuses stranger order (defensible) | refuses stranger's order then ignores Marta's soup; mood inconsistent |
| branic_day_burstoff_036 | L? | unclassified | no orders or tasks all day; very passive for an eager recruit |
| branic_day_burstoff_057 | L? | unclassified | snaps then refuses at 22:58, wakes fully settled next morning |
| branic_day_burstoff_099 | L? | unclassified | First order ignored at 06:40 with no prior provocation shown. |
| branic_day_burstoff_100 | L? | unclassified | Refusals at 14:38 and 19:39 after only mild tension; steep. |
| branic_day_burston_100 | L? | unclassified | refuses order at 14:38 shortly after mocking; still warmly thanks Marta |
| cichy_day_burstoff_058 | L? | unclassified | kindness warmly received at same timestamp as peak tension, jarring |
| cichy_day_burston_014 | L? | unclassified | erupts furiously at 09:38 then looks settled at ease by 10:01 |
| cichy_day_burston_089 | L? | unclassified | full fury outburst at 06:54 with no prior tension buildup |
| cichy_multi_burstoff_099 | L? | unclassified | fury at 12:07 followed by "settled at ease" six minutes later |
| cichy_multi_burston_008 | L? | unclassified | four eruptions across three days; burst saturation not recovering |
| cichy_multi_burston_055 | L? | unclassified | settled at ease 22:16 then fury eruption at 22:40 |
| halgrim_day_burstoff_018 | L? | unclassified | tense from 20:03 with no late provocation to sustain it |
| lutek_day_burston_070 | L? | unclassified | wound tight at 22:04 after only a mocked-and-ignored remark; tension seems high |
| lutek_day_burston_087 | L? | unclassified | wound tight at 22:04 with no clear trigger late evening. |
| lutek_multi_burston_076 | L? | unclassified | extended Day 1 evening tension; stranger kindness ignored |
| lutek_multi_burston_079 | L? | unclassified | kindness ignored twice while tense, atypical for warm character |
| welf_multi_burstoff_050 | L? | unclassified | kindness at 13:23 day 6 gets no-reaction; contradicts pattern |
| welf_multi_burstoff_058 | L? | unclassified | kindness ignored Day 3 18:15 after composed day otherwise |
| welf_multi_burstoff_099 | L? | unclassified | kindness ignored under rain, atypical for this character |
