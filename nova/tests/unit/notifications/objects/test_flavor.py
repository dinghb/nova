#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import copy
import mock

from nova import context
from nova.notifications.objects import flavor as flavor_notification
from nova import objects
from nova.objects import fields
from nova import test
from nova.tests.unit.objects.test_flavor import fake_flavor


class TestFlavorNotification(test.TestCase):
    def setUp(self):
        self.ctxt = context.get_admin_context()
        super(TestFlavorNotification, self).setUp()

    @mock.patch('nova.notifications.objects.flavor.FlavorNotification')
    def _verify_notification(self, flavor_obj, flavor, action,
                             mock_notification, project_id=None):
        notification = mock_notification
        if action == "CREATE":
            flavor_obj.create()
        elif action == "DELETE":
            flavor_obj.destroy()
        elif action == "ADD_ACCESS":
            action = "UPDATE"
            flavor_obj.add_access(project_id)
        elif action == "REMOVE_ACCESS":
            action = "UPDATE"
            flavor_obj.remove_access(project_id)
        else:
            flavor_obj.save()

        self.assertTrue(notification.called)

        event_type = notification.call_args[1]['event_type']
        priority = notification.call_args[1]['priority']
        publisher = notification.call_args[1]['publisher']
        payload = notification.call_args[1]['payload']

        self.assertEqual("fake-mini", publisher.host)
        self.assertEqual("nova-api", publisher.binary)
        self.assertEqual(fields.NotificationPriority.INFO, priority)
        self.assertEqual('flavor', event_type.object)
        self.assertEqual(getattr(fields.NotificationAction, action),
                         event_type.action)
        notification.return_value.emit.assert_called_once_with(self.ctxt)

        schema = flavor_notification.FlavorPayload.SCHEMA
        for field in schema:
            if field in flavor:
                self.assertEqual(flavor[field], getattr(payload, field))

    @mock.patch('nova.objects.Flavor._flavor_create')
    def test_flavor_create_with_notification(self, mock_create):
        flavor = copy.deepcopy(fake_flavor)
        flavor_obj = objects.Flavor(context=self.ctxt)
        flavor_obj.extra_specs = flavor['extra_specs']
        flavorid = '1'
        flavor['flavorid'] = flavorid
        flavor['id'] = flavorid
        mock_create.return_value = flavor
        self._verify_notification(flavor_obj, flavor, 'CREATE')

    @mock.patch('nova.objects.Flavor._flavor_extra_specs_del')
    def test_flavor_update_with_notification(self, mock_delete):
        flavor = copy.deepcopy(fake_flavor)
        flavorid = '1'
        flavor['flavorid'] = flavorid
        flavor['id'] = flavorid
        flavor_obj = objects.Flavor(context=self.ctxt, **flavor)
        flavor_obj.obj_reset_changes()

        del flavor_obj.extra_specs['foo']
        del flavor['extra_specs']['foo']
        self._verify_notification(flavor_obj, flavor, "UPDATE")

        projects = ['project-1', 'project-2']
        flavor_obj.projects = projects
        flavor['projects'] = projects
        self._verify_notification(flavor_obj, flavor, "UPDATE")

    @mock.patch('nova.objects.Flavor._add_access')
    @mock.patch('nova.objects.Flavor._remove_access')
    def test_flavor_access_with_notification(self, mock_remove_access,
                                             mock_add_access):
        flavor = copy.deepcopy(fake_flavor)
        flavorid = '1'
        flavor['flavorid'] = flavorid
        flavor['id'] = flavorid
        flavor_obj = objects.Flavor(context=self.ctxt, **flavor)
        flavor_obj.obj_reset_changes()
        self._verify_notification(flavor_obj, flavor, "ADD_ACCESS",
                                  project_id="project1")
        self._verify_notification(flavor_obj, flavor, "REMOVE_ACCESS",
                                  project_id="project1")

    @mock.patch('nova.objects.Flavor._flavor_destroy')
    def test_flavor_destroy_with_notification(self, mock_destroy):
        flavor = copy.deepcopy(fake_flavor)
        flavorid = '1'
        flavor['flavorid'] = flavorid
        flavor['id'] = flavorid
        mock_destroy.return_value = flavor
        flavor_obj = objects.Flavor(context=self.ctxt, **flavor)
        flavor_obj.obj_reset_changes()
        self._verify_notification(flavor_obj, flavor, "DELETE")

    def test_obj_make_compatible(self):
        flavor = copy.deepcopy(fake_flavor)
        flavorid = '1'
        flavor['flavorid'] = flavorid
        flavor['id'] = flavorid
        flavor_obj = objects.Flavor(context=self.ctxt, **flavor)
        flavor_payload = flavor_notification.FlavorPayload(flavor_obj)
        primitive = flavor_payload.obj_to_primitive()
        self.assertIn('name', primitive['nova_object.data'])
        self.assertIn('swap', primitive['nova_object.data'])
        self.assertIn('rxtx_factor', primitive['nova_object.data'])
        self.assertIn('vcpu_weight', primitive['nova_object.data'])
        self.assertIn('disabled', primitive['nova_object.data'])
        self.assertIn('is_public', primitive['nova_object.data'])
        flavor_payload.obj_make_compatible(primitive['nova_object.data'],
                                           '1.0')
        self.assertNotIn('name', primitive['nova_object.data'])
        self.assertNotIn('swap', primitive['nova_object.data'])
        self.assertNotIn('rxtx_factor', primitive['nova_object.data'])
        self.assertNotIn('vcpu_weight', primitive['nova_object.data'])
        self.assertNotIn('disabled', primitive['nova_object.data'])
        self.assertNotIn('is_public', primitive['nova_object.data'])
