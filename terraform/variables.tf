variable "snowflake_organization" {
  description = "Snowflake organization name (SHOW ORGANIZATION ACCOUNTS)."
  type        = string
}

variable "snowflake_account" {
  description = "Snowflake account name within the organization."
  type        = string
}

variable "snowflake_user" {
  description = "User Terraform authenticates as."
  type        = string
}
