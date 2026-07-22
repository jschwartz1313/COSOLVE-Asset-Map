from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

ROLE_PERMISSIONS = {
    "COSOLVE Viewer": {
        "assets.view_asset",
        "assets.view_relationship",
        "sources.view_source",
        "catalog.view_capability",
        "catalog.view_missionarea",
        "catalog.view_platformdomain",
        "catalog.view_region",
        "catalog.view_strategiccategory",
    },
    "COSOLVE Reviewer": {
        "assets.change_asset",
        "assets.can_verify_asset",
        "sources.change_source",
    },
    "COSOLVE Editor": {
        "assets.add_asset",
        "assets.change_asset",
        "assets.add_relationship",
        "assets.change_relationship",
        "assets.can_export_asset",
        "assets.view_updatesubmission",
        "assets.change_updatesubmission",
        "sources.add_source",
        "sources.change_source",
        "catalog.add_capability",
        "catalog.change_capability",
        "catalog.add_missionarea",
        "catalog.change_missionarea",
        "catalog.add_platformdomain",
        "catalog.change_platformdomain",
        "catalog.add_region",
        "catalog.change_region",
        "catalog.add_strategiccategory",
        "catalog.change_strategiccategory",
    },
    "COSOLVE Publisher": {
        "assets.can_publish_asset",
    },
}


class Command(BaseCommand):
    help = "Create or refresh the standard COSOLVE staff permission groups."

    def handle(self, *args, **options):
        inherited = set()
        for role_name, role_permissions in ROLE_PERMISSIONS.items():
            inherited.update(role_permissions)
            group, _ = Group.objects.get_or_create(name=role_name)
            permissions = []
            for permission_name in inherited:
                app_label, codename = permission_name.split(".", 1)
                permissions.append(
                    Permission.objects.get(
                        content_type__app_label=app_label,
                        codename=codename,
                    )
                )
            group.permissions.set(permissions)
            self.stdout.write(self.style.SUCCESS(f"Configured {role_name}."))
