# -*- coding: utf-8 -*-
from twisted.internet.defer import inlineCallbacks

from globaleaks.db import db_refresh_memory_variables
from globaleaks.db.appdata import load_appdata
from globaleaks.handlers.admin.node import admin_serialize_node
from globaleaks.handlers.base import BaseHandler
from globaleaks.handlers.user import get_user_settings
from globaleaks.models.config import NotificationFactory, PrivateFactory
from globaleaks.models.l10n import NotificationL10NFactory
from globaleaks.models.properties import iso_strf_time
from globaleaks.orm import transact
from globaleaks.rest import requests
from globaleaks.state import State
from globaleaks.utils.mailutils import sendmail
from globaleaks.utils.sets import merge_dicts
from globaleaks.utils.templating import Templating
from globaleaks.utils.utility import log


def admin_serialize_notification(store, language):
    config_dict = NotificationFactory(store).admin_export()

    cmd_flags = {
        'reset_templates': False,
        'exception_email_pgp_key_remove': False,
        'smtp_password': '',
    }

    conf_l10n_dict = NotificationL10NFactory(store).localized_dict(language)

    return merge_dicts(config_dict, cmd_flags, conf_l10n_dict)


def db_get_notification(store, language):
    return admin_serialize_notification(store, language)


@transact
def get_notification(store, language):
    return db_get_notification(store, language)


@transact
def update_notification(store, request, language):
    notif_l10n = NotificationL10NFactory(store)
    notif_l10n.update(request, language)

    if request.pop('reset_templates'):
        appdata = load_appdata()
        notif_l10n.reset_templates(appdata)

    smtp_pw = request.pop('smtp_password', u'')
    if smtp_pw != u'':
        PrivateFactory(store).set_val(u'smtp_password', smtp_pw)

    notif = NotificationFactory(store)
    notif.update(request)

    # Since the Notification object has been changed refresh the global copy.
    db_refresh_memory_variables(store)

    return admin_serialize_notification(store, language)


class NotificationInstance(BaseHandler):
    """
    Manage Notification settings (account details and template)
    """
    check_roles = 'admin'

    def get(self):
        """
        Parameters: None
        Response: AdminNotificationDesc
        Errors: None (return empty configuration, at worst)
        """
        return get_notification(self.request.language)

    def put(self):
        """
        Request: AdminNotificationDesc
        Response: AdminNotificationDesc
        Errors: InvalidInputFormat

        Changes the node notification settings.
        """
        request = self.validate_message(self.request.content.read(),
                                        requests.AdminNotificationDesc)

        return update_notification(request, self.request.language)


class NotificationTestInstance(BaseHandler):
    """
    Send test email notifications to the admin that clicked the button.
    This post takes no arguments and generates an empty response to both
    successful and unsucessful requests. This handler does not return
    until both the db query and the SMTP round trip return.
    """
    check_roles = 'admin'

    @inlineCallbacks
    def post(self):
        user = yield get_user_settings(self.current_user.user_id,
                                       State.tenant_cache[1].default_language)

        language = user['language']

        yield get_notification(language)

        data = {
            'type': 'admin_test_static',
            'node': (yield admin_serialize_node(language)),
            'notification': (yield get_notification(language)),
            'user': user,
        }

        subject, body = Templating().get_mail_subject_and_body(data)

        send_to = user['mail_address']

        yield sendmail(send_to, subject, body)
