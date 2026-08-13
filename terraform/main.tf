# Provisions the Snowflake objects dbt needs. Run this BEFORE `dbt run`.

terraform {
  required_version = ">= 1.5"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
  }
}

provider "snowflake" {
  organization_name = var.snowflake_organization
  account_name      = var.snowflake_account
  user              = var.snowflake_user
  role              = "ACCOUNTADMIN"

  authenticator          = "SNOWFLAKE_JWT"
  private_key            = file(pathexpand(var.snowflake_private_key_path))
  private_key_passphrase = var.snowflake_private_key_passphrase
}

resource "snowflake_warehouse" "alpine" {
  name           = "ALPINE_WH"
  warehouse_size = "XSMALL"
  auto_suspend        = 60
  auto_resume         = true
  initially_suspended = true
  comment = "Managed by Terraform. dbt transforms for ALPINE-WATCH."
}

resource "snowflake_database" "alpine" {
  name    = "ALPINE_WATCH"
  comment = "Managed by Terraform."
}

resource "snowflake_schema" "bronze" {
  database = snowflake_database.alpine.name
  name     = "BRONZE"
  comment  = "Raw landing zone. Loader writes here; dbt only reads."
}

resource "snowflake_account_role" "transformer" {
  name    = "TRANSFORMER"
  comment = "Role dbt assumes. Never use ACCOUNTADMIN for transforms."
}

resource "snowflake_grant_privileges_to_account_role" "warehouse" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.alpine.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "database" {
  account_role_name = snowflake_account_role.transformer.name
  privileges        = ["USAGE", "CREATE SCHEMA"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.alpine.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "bronze_schema" {
  account_role_name = snowflake_account_role.transformer.name
  privileges         = ["USAGE", "CREATE TABLE"]

  on_schema {
    schema_name = "ALPINE_WATCH.BRONZE"
  }
}
