# Generated by Django 3.0.8 on 2020-11-03 09:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("camera_tasks", "0002_cameratask_send_video_to_cloud_threshold"),
    ]

    operations = [
        migrations.AddField(
            model_name="cameratask",
            name="recording_duration",
            field=models.IntegerField(default=1),
        ),
    ]