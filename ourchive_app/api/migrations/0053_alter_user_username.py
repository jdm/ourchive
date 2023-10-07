# Generated by Django 4.2.4 on 2023-10-07 20:20

from django.db import migrations, models
import django_registration.validators


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0052_alter_user_username'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='username',
            field=models.CharField(max_length=150, unique=True, validators=[django_registration.validators.ReservedNameValidator()], verbose_name='Username'),
        ),
    ]
