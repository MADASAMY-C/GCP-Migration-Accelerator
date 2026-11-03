variable "project_id" { type = string }
variable "name_prefix" { type = string }
variable "labels" { type = map(string) }

resource "google_pubsub_topic" "events" {
  name   = "${var.name_prefix}-order-events"
  labels = var.labels
}

resource "google_pubsub_topic" "dlq" {
  name   = "${var.name_prefix}-order-events-dlq"
  labels = var.labels
}

resource "google_pubsub_subscription" "events_dataflow" {
  name                       = "${var.name_prefix}-order-events-dataflow"
  topic                      = google_pubsub_topic.events.name
  ack_deadline_seconds       = 60
  message_retention_duration = "86400s"
  labels                     = var.labels
}

# Inspect bad messages without a consumer: pull this subscription manually.
resource "google_pubsub_subscription" "dlq_inspect" {
  name                 = "${var.name_prefix}-order-events-dlq-inspect"
  topic                = google_pubsub_topic.dlq.name
  ack_deadline_seconds = 30
}

output "topic_name" { value = google_pubsub_topic.events.name }
output "subscription_name" { value = google_pubsub_subscription.events_dataflow.name }
output "dlq_topic_name" { value = google_pubsub_topic.dlq.name }
