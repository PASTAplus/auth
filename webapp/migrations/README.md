# Database migrations

This directory contains database migrations for the 

We don't have formally a versioned database schema, and we probably won't need a fully automated migration system for Auth. So at least for now, we'll just manually write migration scripts as needed.

We are initially using SQLite3 for the database. SQLite3 has limited in-place editing of table structures, so the general procedure for migrations is to create a new table with the desired schema, copy the data from the old table to the new table, drop the old table, and rename the new table to the old table.

## Foreign keys and transactions

SQLite3 supports foreign keys, but they are not enforced by default. Foreign keys are enforced in the app, but not in the migration scripts. So we can manipulate the tables in multiple steps without transactions, as long as the tables have the proper foreign key referential integrity by the time the app is started. Note that this also means that there are no warnings or errors if the foreign key constraints are violated during the migration process.

## Running migrations

To run a migration, execute the SQL script in the SQLite3 database. For example:

```bash
sqlite3 auth.sqlite3 < 001.sql
```

