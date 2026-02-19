"""
wsz6_portal/db_router.py

Routes wsz6_play models to the 'gdm' database.
All other models use the 'default' (UARD) database.
"""


class GDMRouter:
    """
    A database router that sends wsz6_play models to the 'gdm' database
    and everything else to 'default'.
    """

    GDM_APP = 'wsz6_play'

    def db_for_read(self, model, **hints):
        if model._meta.app_label == self.GDM_APP:
            return 'gdm'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == self.GDM_APP:
            return 'gdm'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # Allow relations within the same database.
        db_set = {self.GDM_APP}
        if obj1._meta.app_label in db_set and obj2._meta.app_label in db_set:
            return True
        if obj1._meta.app_label not in db_set and obj2._meta.app_label not in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == self.GDM_APP:
            return db == 'gdm'
        return db == 'default'
