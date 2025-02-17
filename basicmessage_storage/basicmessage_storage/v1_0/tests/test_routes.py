import json

import asynctest
from aries_cloudagent.admin.request_context import AdminRequestContext
from aries_cloudagent.protocols.basicmessage.v1_0 import routes as base_module
from asynctest import TestCase as AsyncTestCase
from asynctest import mock as async_mock

from basicmessage_storage.v1_0.models import BasicMessageRecord

from .. import routes as test_module
from ..routes import all_messages_list, plugin_connections_send_message


class TestRoutes(AsyncTestCase):
    async def setUp(self) -> None:
        self.session_inject = {}
        self.context = AdminRequestContext.test_context(self.session_inject)
        self.request_dict = {
            "context": self.context,
            "outbound_message_router": async_mock.CoroutineMock(),
        }
        self.request = async_mock.MagicMock(
            app={},
            match_info={},
            query={},
            __getitem__=lambda _, k: self.request_dict[k],
        )
        self.test_conn_id = "connection-id"

    @asynctest.patch.object(base_module, "ConnRecord", autospec=True)
    @asynctest.patch.object(test_module, "BasicMessageRecord", autospec=True)
    async def test_plugin_connections_send_message_saves_record(
        self, mock_basic_message_rec_class, _
    ):
        self.request.json = async_mock.CoroutineMock()
        self.request.json.return_value = {"content": "content"}
        self.request.match_info = {"conn_id": self.test_conn_id}

        mock_basic_message_rec = async_mock.MagicMock(save=async_mock.CoroutineMock())
        mock_basic_message_rec_class.deserialize.return_value = mock_basic_message_rec
        res = await plugin_connections_send_message(self.request)

        mock_basic_message_rec.save.assert_called()
        assert res is not None

    @asynctest.patch.object(base_module, "ConnRecord", autospec=True)
    @asynctest.patch.object(test_module, "BasicMessageRecord", autospec=True)
    async def test_plugin_connections_send_message_raises_exception_when_save_fails(
        self, mock_basic_message_rec_class, _
    ):
        self.request.json = async_mock.CoroutineMock()
        self.request.json.return_value = {"content": "content"}
        self.request.match_info = {"conn_id": self.test_conn_id}

        # Mock an exception during save
        mock_basic_message_rec = async_mock.MagicMock(
            save=lambda: (_ for _ in ()).throw(Exception("test"))
        )
        mock_basic_message_rec_class.deserialize.return_value = mock_basic_message_rec

        with self.assertRaises(Exception):
            await plugin_connections_send_message(self.request)

    @asynctest.patch.object(base_module, "ConnRecord", autospec=True)
    @asynctest.patch.object(test_module, "BasicMessageRecord", autospec=True)
    async def test_all_messages_list_succeeds_and_sorts(self, mock_basic_message_rec_class, _):
        mock_basic_message_rec_class.query = async_mock.CoroutineMock()
        mock_basic_message_rec_class.query.return_value = [
            BasicMessageRecord(record_id="2", created_at="2023-10-13T21:49:14Z"),
            BasicMessageRecord(record_id="1", created_at="2023-10-13T20:49:14Z"),
            BasicMessageRecord(record_id="0", created_at="2023-10-13T22:49:14Z"),
        ]
        response = await all_messages_list(self.request)
        results = json.loads(response.body)['results']

        mock_basic_message_rec_class.query.assert_called()
        assert results[0]['created_at'] == '2023-10-13T22:49:14Z'
        assert results[2]['created_at'] == '2023-10-13T20:49:14Z'

    async def test_register(self):
        mock_app = async_mock.MagicMock()
        mock_app.add_routes = async_mock.MagicMock()

        await test_module.register(mock_app)
        mock_app.add_routes.assert_called()

    async def test_post_process_routes(self):
        mock_app = async_mock.MagicMock(_state={"swagger_dict": {}})
        test_module.post_process_routes(mock_app)
        assert "tags" in mock_app._state["swagger_dict"]
