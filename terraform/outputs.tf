output "warehouse_name" {
  description = "Feed this into the dbt profile."
  value       = snowflake_warehouse.alpine.name
}

output "database_name" {
  value = snowflake_database.alpine.name
}

output "transformer_role" {
  value = snowflake_account_role.transformer.name
}
