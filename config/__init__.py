# PyMySQL fallback for MySQL on hosts without mysqlclient C headers (e.g. PythonAnywhere)
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
