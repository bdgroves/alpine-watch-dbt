# Provisions the Snowflake objects dbt needs. Run this BEFORE `dbt run`.
#
# ⚠  VERSION WARNING: the Snowflake Terraform provider churned hard.
#    It moved namespace (Snowflake-Labs -> snowflakedb) and renamed
#    resources at v1 (snowflake_role -> snowflake_account_role, and the
#    grant resources were reworked entirely). Check the current registry
#    docs before you trust the resource names below.

terraform {
  required_version = ">= 1.5"

  required_providers {
    snowflake = {
      source  = "snowflakedb/snowflake"
      version = "~> 2.0"
    }
  }

  # Local state is fine solo. On a team this becomes an S3/Azure backend
  # with locking, so two people can't apply over each other.
  # backend "azurerm" { ... }
}

provider "snowflake" {
  organization_name = var.snowflake_organization
  account_name      = var.snowflake_account
  user              = var.snowflake_user
  role              = "SYSADMIN"
}

# ---------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------

resource "snowflake_warehouse" "alpine" {
  name           = "ALPINE_WH"
  warehouse_size = "XSMALL"

  # Cost-aware design, which the posting calls out explicitly.
  # Suspend fast, resume on demand. An idle warehouse is pure burn.
  auto_suspend        = 60
  auto_resume         = true
  initially_suspended = true

  comment = "Managed by Terraform. dbt transforms for ALPINE-WATCH."
}

# ---------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------

resource "snowflake_database" "alpine" {
  name    = "ALPINE_WATCH"
  comment = "Managed by Terraform."
}

resource "snowflake_schema" "bronze" {
  database = snowflake_database.alpine.name
  name     = "BRONZE"
  comment  = "Raw landing zone. Loader writes here; dbt only reads."
}

# ---------------------------------------------------------------------
# Access
# ---------------------------------------------------------------------

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
