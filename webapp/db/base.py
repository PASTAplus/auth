import sqlalchemy.orm

mapper_registry = sqlalchemy.orm.registry()
Base = mapper_registry.generate_base()
mapper_registry.configure()

# Import table modules to register them with Base.metadata
# import db.group
# import db.identity
# import db.permission
# import db.profile
# import db.sync

