# Loan Risk Target Definition

## Purpose

The assessment asks for a model that predicts the risk of a loan application, but it does not provide a formal definition of "risk." For the initial model, loan risk is defined as the probability that a funded loan will result in an adverse repayment outcome.

This is a credit-risk target. It is not a prediction of whether an application will be approved or funded.

## Prediction Point

The primary POC prediction is made before pricing and before the lending decision or any repayment outcomes are known. Model features must therefore be limited to information available at that point.

Fields produced after the decision or during repayment must not be used as predictors. These include `approved`, `originated`, `originatedDate`, `isFunded`, `loanStatus`, `fpStatus`, and payment records.

Because the score may inform APR and repayment terms, the `pre_pricing_v1` feature contract excludes `apr` and `originallyScheduledPaymentAmount`. The older post-pricing experiment includes them only as an ablation reference; it is not the primary feature contract.

## Primary Target

The initial model uses a binary target named `adverse_outcome`:

- `0` - good outcome
- `1` - bad outcome

### Good outcome

A loan is labelled good when:

```text
loanStatus = "Paid Off Loan"
```

This indicates that the borrower completed the expected repayment obligation.

### Bad outcome

A loan is labelled bad when `loanStatus` is one of:

```text
Internal Collection
External Collection
Settled Bankruptcy
Charged Off
```

These statuses represent severe repayment difficulty or a likely financial loss.

## Modeling Population

Only funded loans with a resolved, unambiguous good or bad outcome are included in the initial training population.

Applications that were rejected, withdrawn, voided, or never funded are excluded because no repayment outcome can be observed. Training on funded loans means the model estimates:

```text
P(bad repayment outcome | funded loan, application-time information)
```

It does not directly estimate the risk of every applicant in the original application population.

## Initial Data-Quality Finding

During the initial dataset scan, three records were found with `loanStatus = "Internal Collection"` even though `isFunded = 0`. All three also have `approved = False`, `originated = False`, no origination date, and no matching payment records. A broader terminal-outcome check found one additional unfunded record labelled `Settled Bankruptcy`; it was also unapproved and unoriginated, with `fpStatus = "No Payments"`. There is therefore no supporting evidence that these four loans were issued or entered a real collection or bankruptcy outcome.

These records are treated as source-data inconsistencies. The pipeline detects and reports unfunded loans carrying a configured terminal outcome, quarantines them from target construction, and records the number excluded in the training-run metadata. The check is non-blocking for this historical dataset so that known dirty records do not stop an otherwise valid run.

The target population must satisfy both conditions:

```text
isFunded = 1
loanStatus is in the configured good or bad terminal-status set
```

The anomalous records should be investigated with the data owner in a production setting rather than automatically corrected or assigned a target.

## Excluded and Ambiguous Outcomes

The following statuses are excluded from the initial target rather than being assigned a potentially incorrect label:

- `New Loan` - the repayment outcome has not matured.
- `Returned Item` - represents one missed payment and does not necessarily imply default.
- `Pending Paid Off` - the final outcome is not yet confirmed.
- `Settlement Pending Paid Off` - the final outcome is not yet confirmed.
- `Settlement Paid Off` - the loan was repaid through settlement, but the business loss threshold is unclear.
- `Charged Off Paid Off` - contains both a serious delinquency event and eventual repayment.
- Missing or unknown status - insufficient information for a reliable label.
- Voided loans - no meaningful repayment performance was observed.

The supplied MoneyLion data dictionary does not define `Settlement Paid Off` or `Charged Off Paid Off`; it only describes selected statuses such as `Returned Item`, `Rejected`, `Withdrawn Application`, and statuses containing "void." Any interpretation of the two ambiguous paid-off statuses is therefore a modeling assumption rather than a documented business rule.

The primary baseline excludes both statuses. They should be reviewed with business stakeholders, and separately configured sensitivity analyses can test whether either or both should be treated as adverse. The primary baseline must not be overwritten by those experiments.

## Leakage Controls

Identifiers and outcome-related fields are not model features:

- `loanId`, `anon_ssn`, `clarityFraudId`, and `underwritingid` are excluded as raw predictors.
- `loanStatus` is used only to construct the label.
- `fpStatus` and the payment table contain post-application outcomes and are excluded from application-time features.
- Historical borrower features may be used only when calculated from events occurring before the current application date.

## Limitations

### Selection bias

Repayment labels are observable only for loans that were historically funded. The training population was selected by the previous underwriting process, so performance on previously rejected applicants cannot be measured directly.

### Outcome maturity

The dataset provides current loan status rather than a clearly defined outcome window. Recent loans may not have had enough time to default or repay. Unresolved loans are excluded, and future work should introduce a fixed performance window where the available dates permit it.

### Business cost

The binary target treats all bad outcomes equally, although the financial impact depends on exposure, recovered payments, fees, and collection costs. Model evaluation and threshold selection should eventually incorporate expected monetary loss.

## Possible Secondary Targets

The following targets may be evaluated separately but should not replace the primary target without a clear business reason:

- **First-payment failure:** predict a rejected or returned first payment using `fpStatus` or the first payment record as the label.
- **Collection risk:** predict whether a loan enters internal or external collection.
- **Expected loss:** predict the unrecovered monetary amount rather than a binary outcome.
- **Approval or funding:** predict the historical `approved` or `isFunded` decision. This imitates the prior underwriting policy and is not itself a repayment-risk target.

## Initial Assumption

Until a business owner supplies a formal default policy, the primary binary definition above will be used as the reproducible baseline. The status mapping, exclusions, population filters, and label version should be recorded with every training run.
