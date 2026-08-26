assignemnts

1. generate a lightGBM ML model - to predict laon risk
2. write documentation & system design for an automated ML SYSTEM
3. build an automated ML systems

datasets:

1. loan (loan appliation) / loans that have been funded
2. underwriting variables
3. payment data

install venv install python

# part 1 - thought process

1. loan risk - what does it mean ? risk fo whawt? risk of defaulting (credit default)
2. understand if data are only loan applications or we also have examples where people who have defaulted?
3. funded loans - loan whose money has already been given (this is the step after originating a loan)
4. Separate the datasets , excluding ambiguous outcomes or unmatured loans
5. adverse payment - negative repayment outcome due to whatever reason.
6. lightGBM model -> binary classification -> produces probability
7. have to decide a decision threshold , i.e. > 50% is considered risky? a baseline threshold of 50% is set.
8. metrics:
   roc-auc -> how % all the time a bad loan is selected over a good loan
   pr-auc -> how reliable a model identify bad loan while incorrectly flagging good loans
   log loss -> error of preddiction lower better

# part 2 & 3

1. pydantic - to validate schema
2. fastAPI - to serve api
3. offlien learning but online inference
4. decouple every components, separation gives each pipeline a clear contract and improves independent testing , reproducibility
5. need to validate model! offline validation step before raising the challenger
6. logging real time results (online)
7. application time data should enter drift monitoring immediately even without outcome label / ground truth
