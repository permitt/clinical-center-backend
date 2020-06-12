from django.core.management.base import BaseCommand, CommandError
from users.models import ClinicAdmin

class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        self.stdout.write("Writing progress test!")

        self.stdout.write(ClinicAdmin.objects.all()[0].firstName)

