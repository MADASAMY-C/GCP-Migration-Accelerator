-- Batch scoring -> ml.churn_predictions (also scheduled from the Airflow DAG)
INSERT INTO `${PROJECT_ID}.ml.churn_predictions` (customer_id, churn_probability, model, scored_at)
SELECT customer_id,
       (SELECT p.prob FROM UNNEST(predicted_churned_probs) p WHERE p.label = 1),
       'bqml_logreg', CURRENT_TIMESTAMP()
FROM ML.PREDICT(MODEL `${PROJECT_ID}.ml.churn_logreg`, TABLE `${PROJECT_ID}.ml.ml_churn_scoring`);
