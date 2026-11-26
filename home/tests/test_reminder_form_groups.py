from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from home.reminder_forms import RegulatoryReminderForm, MilestoneForm
from profile.models import Reminder


@override_settings(SECURE_SSL_REDIRECT=False)
class ReminderFormGroupTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('reminder-form-groups')
        self.client.force_login(self.user)

    def test_forms_offer_only_their_own_types(self):
        regulatory = RegulatoryReminderForm(user=self.user)
        milestone = MilestoneForm(user=self.user)
        self.assertEqual({key for key, _ in regulatory.fields['kind'].choices}, {'expiration', 'flight_review', 'instructor_renewal', 'ipc'})
        self.assertEqual({key for key, _ in milestone.fields['kind'].choices},
                         {'flight_time', 'time_in_type', 'crew_in_type', 'company_time', 'flight_condition'})
        self.assertFalse(RegulatoryReminderForm({'kind': 'flight_time', 'target_hours': '100'}, user=self.user).is_valid())
        self.assertFalse(MilestoneForm({'kind': 'expiration', 'title': 'IPC', 'due_date': '2027-01-01'}, user=self.user).is_valid())

    def test_group_links_open_the_correct_form(self):
        for group, kind, label in [('regulatory', 'expiration', 'Custom'),
                                    ('milestones', 'flight_time', 'Total flight time')]:
            response = self.client.get(reverse('manage_reminders'), {'group': group})
            self.assertContains(response, label)
            self.assertEqual(response.context['form'].initial['kind'], kind)

    def test_browser_submission_stays_in_its_group(self):
        response = self.client.post(reverse('manage_reminders') + '?group=milestones', {
            'reminder_group': 'milestones', 'kind': 'flight_time', 'target_hours': '100',
        })
        self.assertRedirects(response, reverse('manage_reminders') + '?group=milestones')
        obj = Reminder.objects.get(user=self.user)
        response = self.client.get(reverse('edit_reminder', args=[obj.pk]))
        self.assertIsInstance(response.context['form'], MilestoneForm)
        response = self.client.post(reverse('manage_reminders') + '?group=regulatory', {
            'reminder_group': 'regulatory', 'kind': 'flight_time', 'target_hours': '200',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('kind', response.context['form'].errors)
        self.assertEqual(Reminder.objects.filter(user=self.user).count(), 1)

    def test_management_pages_only_show_their_own_saved_records(self):
        Reminder.objects.create(user=self.user, kind='expiration', title='IPC check', due_date='2027-01-01')
        Reminder.objects.create(user=self.user, kind='flight_time', title='Hours goal', target_hours='12345')
        regulatory = self.client.get(reverse('manage_reminders'), {'group': 'regulatory'})
        milestones = self.client.get(reverse('manage_reminders'), {'group': 'milestones'})
        self.assertEqual([section['key'] for section in regulatory.context['reminder_groups']], ['regulatory'])
        self.assertEqual([section['key'] for section in milestones.context['reminder_groups']], ['milestones'])
        self.assertContains(regulatory, 'IPC check')
        self.assertNotContains(milestones, 'IPC check')
        self.assertContains(milestones, 'Total 0.0/12345')
        self.assertNotContains(regulatory, 'Total 0.0/12345')
        self.assertNotContains(milestones, 'id="medical-heading"')
