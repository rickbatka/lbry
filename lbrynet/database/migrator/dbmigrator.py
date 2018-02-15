import logging


def migrate_db(db_dir, start, end):
    current = start
    while current < end:
        if current == 1:
            from lbrynet.database.migrator.migrate1to2 import do_migration
            do_migration(db_dir)
        elif current == 2:
            from lbrynet.database.migrator.migrate2to3 import do_migration
            do_migration(db_dir)
        elif current == 3:
            from lbrynet.database.migrator.migrate3to4 import do_migration
            do_migration(db_dir)
        elif current == 4:
            from lbrynet.database.migrator.migrate4to5 import do_migration
            do_migration(db_dir)
        elif current == 5:
            from lbrynet.database.migrator.migrate5to6 import do_migration
            do_migration(db_dir)
        else:
            raise Exception("DB migration of version {} to {} is not available".format(current,
                                                                                       current+1))
        current += 1
    return None


def run_migration_script():
    import sys
    log_format = "(%(asctime)s)[%(filename)s:%(lineno)s] %(funcName)s(): %(message)s"
    logging.basicConfig(level=logging.DEBUG, format=log_format, filename="migrator.log")
    sys.stdout = open("migrator.out.log", 'w')
    sys.stderr = open("migrator.err.log", 'w')
    migrate_db(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))


if __name__ == "__main__":
    run_migration_script()
