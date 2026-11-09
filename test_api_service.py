import unittest
from unittest import mock

import requests

import _soporte  # noqa: F401  (ajusta sys.path)
from servicios import api_service as api


def _resp(json_data=None, status=200, json_error=False):
    r = mock.Mock()
    r.status_code = status
    if status >= 400:
        r.raise_for_status.side_effect = requests.exceptions.HTTPError(
            f"{status}"
        )
    else:
        r.raise_for_status.return_value = None
    if json_error:
        r.json.side_effect = ValueError("no json")
    else:
        r.json.return_value = json_data
    return r


OK = {
    "result": "success",
    "time_last_update_utc": "Mon, 09 Nov 2026 00:00:01 +0000",
    "rates": {"NIO": 36.6, "USD": 1},
}


class TestAPI(unittest.TestCase):

    def setUp(self):
        api._cache.update(momento=0.0, datos=None)

    @mock.patch("requests.get")
    def test_respuesta_correcta(self, get):
        get.return_value = _resp(OK)
        d = api.consultar_tasa_cordoba()
        self.assertEqual(d["nio_por_usd"], 36.6)
        self.assertEqual(get.call_args.kwargs["timeout"], api.TIMEOUT)

    @mock.patch("requests.get")
    def test_cache(self, get):
        get.return_value = _resp(OK)
        api.consultar_tasa_cordoba()
        api.consultar_tasa_cordoba()
        self.assertEqual(get.call_count, 1)
        api.consultar_tasa_cordoba(usar_cache=False)
        self.assertEqual(get.call_count, 2)

    @mock.patch("requests.get", side_effect=requests.exceptions.Timeout)
    def test_timeout(self, _):
        with self.assertRaisesRegex(api.ErrorAPI, "tiempo de espera"):
            api.consultar_tasa_cordoba()

    @mock.patch("requests.get",
                side_effect=requests.exceptions.ConnectionError)
    def test_sin_internet(self, _):
        with self.assertRaisesRegex(api.ErrorAPI, "Internet"):
            api.consultar_tasa_cordoba()

    @mock.patch("requests.get")
    def test_http_500(self, get):
        get.return_value = _resp(status=500)
        with self.assertRaises(api.ErrorAPI):
            api.consultar_tasa_cordoba()

    @mock.patch("requests.get")
    def test_json_invalido(self, get):
        get.return_value = _resp(json_error=True)
        with self.assertRaisesRegex(api.ErrorAPI, "JSON"):
            api.consultar_tasa_cordoba()

    @mock.patch("requests.get")
    def test_sin_nio_o_tasa_mala(self, get):
        get.return_value = _resp({"result": "success", "rates": {}})
        with self.assertRaisesRegex(api.ErrorAPI, "NIO"):
            api.consultar_tasa_cordoba()
        get.return_value = _resp(
            {"result": "success", "rates": {"NIO": 0}}
        )
        with self.assertRaises(api.ErrorAPI):
            api.consultar_tasa_cordoba()

    def test_conversiones(self):
        self.assertEqual(api.cordobas_a_dolares(3660, 36.6), 100.0)
        self.assertEqual(api.dolares_a_cordobas(100, 36.6), 3660.0)
        with self.assertRaises(ValueError):
            api.cordobas_a_dolares(-1, 36.6)
        with self.assertRaises(ValueError):
            api.cordobas_a_dolares(100, 0)


if __name__ == "__main__":
    unittest.main()
