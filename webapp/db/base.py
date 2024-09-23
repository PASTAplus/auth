import sqlalchemy.orm

mapper_registry = sqlalchemy.orm.registry()
Base = mapper_registry.generate_base()
mapper_registry.configure()
