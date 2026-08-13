variable "snowflake_organization" {
  type = string
}

variable "snowflake_account" {
  type = string
}

variable "snowflake_user" {
  type = string
}

variable "snowflake_private_key_path" {
  type = string
}

variable "snowflake_private_key_passphrase" {
  type      = string
  sensitive = true
}
