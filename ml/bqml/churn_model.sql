-- BigQuery ML baseline: logistic regression churn model (run: python -m accelerator.sqlutil ml/bqml/churn_model.sql)
CREATE OR REPLACE MODEL `${PROJECT_ID}.ml.churn_logreg`
OPTIONS (
  model_type = 'LOGISTIC_REG',
  input_label_cols = ['churned'],
  auto_class_weights = TRUE,
  data_split_method = 'RANDOM',
  data_split_eval_fraction = 0.2,
  l2_reg = 0.1
) AS
SELECT recency_days, frequency, monetary, avg_order_value, bad_orders, churned
FROM `${PROJECT_ID}.ml.ml_churn_training`;

-- Evaluation metrics (precision, recall, accuracy, f1, log_loss, roc_auc)
SELECT * FROM ML.EVALUATE(MODEL `${PROJECT_ID}.ml.churn_logreg`);
