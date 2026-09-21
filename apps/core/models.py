from django.db import models


class CompletedRelease(models.Model):
    version = models.CharField(max_length=64, primary_key=True)
    completed_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.version
