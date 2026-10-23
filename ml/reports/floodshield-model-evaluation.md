# FloodShield Marala — model accuracy, class F1, and confusion matrices

AI FloodShield PAK, Chenab at Marala Headworks.

Holdout scores for the seven selected horizon models. Training days are monsoon seasons 2024–2025. The test set is monsoon 2026. Accuracy was not the rule used to pick a model.

Report date: 22 October 2026.  
Source: `models/metrics/horizon_metrics.json`, version `floodshield-marala-7day-2`.

## Summary

- **Pooled accuracy: 98.60%** (635 correct of 644 test days).
- **Mean macro-F1, Day +1 through Day +6: 49.64%.**
- **Low-class F1: 0.000** on every horizon that has a Low example.

The 2026 labels are almost all Normal. Days +1 to +6 each contain one Low day and no Medium, High, Very High, or Exceptional day. Every selected model missed that Low day, so flood-class F1 is zero even while overall accuracy stays near 99%. Day +7 has no minority class in the test set, so its 0.994 macro-F1 is Normal only. Very High has no historical examples. Exceptional has one, which is below the two-example minimum, so neither class was trained and neither has an F1.

## Selected model by horizon

| Horizon | Model | Test rows | Correct | Accuracy | Macro-F1 | Classes in macro-F1 |
|---|---|---:|---:|---:|---:|---|
| Day +1 | Random Forest, unweighted | 97 | 95 | 97.94% | 0.495 | Normal, Low |
| Day +2 | Majority baseline | 95 | 94 | 98.95% | 0.497 | Normal, Low |
| Day +3 | Random Forest, balanced | 94 | 92 | 97.87% | 0.495 | Normal, Low |
| Day +4 | Random Forest, unweighted | 93 | 92 | 98.92% | 0.497 | Normal, Low |
| Day +5 | Random Forest, unweighted | 90 | 89 | 98.89% | 0.497 | Normal, Low |
| Day +6 | Majority baseline | 88 | 87 | 98.86% | 0.497 | Normal, Low |
| Day +7 | Random Forest, balanced | 87 | 86 | 98.85% | 0.994 | Normal only |

Pooled accuracy is 635 correct predictions divided by 644 test rows. Macro-F1 averages F1 only over classes present in that horizon’s 2026 test set.

## F1 score for each class

A dash means the class has no score: it is missing from the 2026 test set, or it was unsupported in training.

| Horizon | Normal | Low | Medium | High | Very High | Exceptional |
|---|---:|---:|---:|---:|---:|---:|
| Day +1 | 0.990 | 0.000 | — | — | — | — |
| Day +2 | 0.995 | 0.000 | — | — | — | — |
| Day +3 | 0.989 | 0.000 | — | — | — | — |
| Day +4 | 0.995 | 0.000 | — | — | — | — |
| Day +5 | 0.994 | 0.000 | — | — | — | — |
| Day +6 | 0.994 | 0.000 | — | — | — | — |
| Day +7 | 0.994 | — | — | — | — | — |

Exact scored values: Day +1 Normal 0.9896; Day +2 Normal 0.9947; Day +3 Normal 0.9892; Day +4 Normal 0.9946; Day +5 Normal 0.9944; Day +6 Normal 0.9943; Day +7 Normal 0.9942. Low F1 is exactly 0 wherever a Low day exists. Day +7 predicted Low once, but there was no true Low day, so Low F1 is not defined.

## Confusion matrices

Rows are the true 2026 label. Columns are the prediction. Class order is Normal, Low, Medium, High, Very High, Exceptional. Every Medium, High, Very High, and Exceptional cell is zero.

### Day +1 · Random Forest, unweighted

95 correct of 97. Accuracy 97.94%.

| True \ Pred | Normal | Low | Medium | High | Very High | Exceptional |
|---|---:|---:|---:|---:|---:|---:|
| Normal | 95 | 1 | 0 | 0 | 0 | 0 |
| Low | 1 | 0 | 0 | 0 | 0 | 0 |
| Medium | 0 | 0 | 0 | 0 | 0 | 0 |
| High | 0 | 0 | 0 | 0 | 0 | 0 |
| Very High | 0 | 0 | 0 | 0 | 0 | 0 |
| Exceptional | 0 | 0 | 0 | 0 | 0 | 0 |

### Day +2 · Majority baseline

94 correct of 95. Accuracy 98.95%.

| True \ Pred | Normal | Low | Medium | High | Very High | Exceptional |
|---|---:|---:|---:|---:|---:|---:|
| Normal | 94 | 0 | 0 | 0 | 0 | 0 |
| Low | 1 | 0 | 0 | 0 | 0 | 0 |
| Medium | 0 | 0 | 0 | 0 | 0 | 0 |
| High | 0 | 0 | 0 | 0 | 0 | 0 |
| Very High | 0 | 0 | 0 | 0 | 0 | 0 |
| Exceptional | 0 | 0 | 0 | 0 | 0 | 0 |

### Day +3 · Random Forest, balanced

92 correct of 94. Accuracy 97.87%.

| True \ Pred | Normal | Low | Medium | High | Very High | Exceptional |
|---|---:|---:|---:|---:|---:|---:|
| Normal | 92 | 1 | 0 | 0 | 0 | 0 |
| Low | 1 | 0 | 0 | 0 | 0 | 0 |
| Medium | 0 | 0 | 0 | 0 | 0 | 0 |
| High | 0 | 0 | 0 | 0 | 0 | 0 |
| Very High | 0 | 0 | 0 | 0 | 0 | 0 |
| Exceptional | 0 | 0 | 0 | 0 | 0 | 0 |

### Day +4 · Random Forest, unweighted

92 correct of 93. Accuracy 98.92%.

| True \ Pred | Normal | Low | Medium | High | Very High | Exceptional |
|---|---:|---:|---:|---:|---:|---:|
| Normal | 92 | 0 | 0 | 0 | 0 | 0 |
| Low | 1 | 0 | 0 | 0 | 0 | 0 |
| Medium | 0 | 0 | 0 | 0 | 0 | 0 |
| High | 0 | 0 | 0 | 0 | 0 | 0 |
| Very High | 0 | 0 | 0 | 0 | 0 | 0 |
| Exceptional | 0 | 0 | 0 | 0 | 0 | 0 |

### Day +5 · Random Forest, unweighted

89 correct of 90. Accuracy 98.89%.

| True \ Pred | Normal | Low | Medium | High | Very High | Exceptional |
|---|---:|---:|---:|---:|---:|---:|
| Normal | 89 | 0 | 0 | 0 | 0 | 0 |
| Low | 1 | 0 | 0 | 0 | 0 | 0 |
| Medium | 0 | 0 | 0 | 0 | 0 | 0 |
| High | 0 | 0 | 0 | 0 | 0 | 0 |
| Very High | 0 | 0 | 0 | 0 | 0 | 0 |
| Exceptional | 0 | 0 | 0 | 0 | 0 | 0 |

### Day +6 · Majority baseline

87 correct of 88. Accuracy 98.86%.

| True \ Pred | Normal | Low | Medium | High | Very High | Exceptional |
|---|---:|---:|---:|---:|---:|---:|
| Normal | 87 | 0 | 0 | 0 | 0 | 0 |
| Low | 1 | 0 | 0 | 0 | 0 | 0 |
| Medium | 0 | 0 | 0 | 0 | 0 | 0 |
| High | 0 | 0 | 0 | 0 | 0 | 0 |
| Very High | 0 | 0 | 0 | 0 | 0 | 0 |
| Exceptional | 0 | 0 | 0 | 0 | 0 | 0 |

### Day +7 · Random Forest, balanced

86 correct of 87. Accuracy 98.85%. No true Low day; one Normal day was called Low.

| True \ Pred | Normal | Low | Medium | High | Very High | Exceptional |
|---|---:|---:|---:|---:|---:|---:|
| Normal | 86 | 1 | 0 | 0 | 0 | 0 |
| Low | 0 | 0 | 0 | 0 | 0 | 0 |
| Medium | 0 | 0 | 0 | 0 | 0 | 0 |
| High | 0 | 0 | 0 | 0 | 0 | 0 |
| Very High | 0 | 0 | 0 | 0 | 0 | 0 |
| Exceptional | 0 | 0 | 0 | 0 | 0 | 0 |

## Test-set support

Counts of true labels in the 2026 test window.

| Horizon | Normal | Low | Medium | High | Very High | Exceptional |
|---|---:|---:|---:|---:|---:|---:|
| Day +1 | 96 | 1 | 0 | 0 | 0 | 0 |
| Day +2 | 94 | 1 | 0 | 0 | 0 | 0 |
| Day +3 | 93 | 1 | 0 | 0 | 0 | 0 |
| Day +4 | 92 | 1 | 0 | 0 | 0 | 0 |
| Day +5 | 89 | 1 | 0 | 0 | 0 | 0 |
| Day +6 | 87 | 1 | 0 | 0 | 0 | 0 |
| Day +7 | 87 | 0 | 0 | 0 | 0 | 0 |

Full historical inflow labels: Normal 316, Low 14, Medium 3, High 2, Very High 0, Exceptional 1.
