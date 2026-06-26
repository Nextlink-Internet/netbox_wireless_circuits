import csv
import io
from datetime import date
from decimal import Decimal

from django.test import TestCase

from circuits.models import Circuit, CircuitType, Provider

from netbox_wireless_circuits.importers import get_source
from netbox_wireless_circuits.importers.base import (
    clean_excel,
    dms_to_decimal,
    normalize_band,
    normalize_modulation,
    to_decimal,
    to_int,
)
from netbox_wireless_circuits.choices import rollup_license_status
from netbox_wireless_circuits.importers.comsearch import ComsearchCSVSource
from netbox_wireless_circuits.importers.engine import run_import
from netbox_wireless_circuits.models import (
    WirelessImportStatusMap,
    WirelessLicenseProfile,
)


# A representative Comsearch row (only the columns the adapter reads).
BASE_ROW = {
    "site1": "TX-THROCKMORTON-WE-2", "state1": "TX", "county1": "Throckmorton County",
    "site2": "TX-THROCKMORTON-SW-2", "state2": "TX", "county2": "Haskell County",
    "band": "11 GHz (10700-11700 MHz) US",
    "rcn": '="260623C5"', "job number": "260623COMSRP02",
    "Current PCN Date": "06/23/2026",
    "status1": "Proposed", "status2": "Licensed",
    "licensebasis1": "Primary", "licensebasis2": "Primary",
    "conditional authorization1": "No", "conditional authorization2": "No",
    "application date1": "06/18/2026", "application date2": "06/18/2026",
    "effective date1": "05/27/2026", "effective date2": "05/27/2026",
    "expiration date1": "06/23/2030", "expiration date2": "12/17/2029",
    "company1": "AMG Technology Investment Group LLC", "call1": "WRHV300",
    "radio service1": "CF-Common Carrier Fixed", "station class1": "FXO-Fixed",
    "planbandwidth1(MHz)": "80.0",
    "distance(km)": "18.927", "distance(mi)": "11.760",
    "atmosphericLoss(dB)": "0.32", "freeSpaceLoss(dB)": "138.97",
    "latitude1": "33 10 52.86 N", "longitude1": "99 22 55.02 W",
    "latitude2": "33 01 56.86 N", "longitude2": "99 28 51.74 W",
    "ground1(m)": "509.02", "ground1(ft)": "1670.0",
    "ground2(m)": "504.26", "ground2(ft)": "1654.4",
    "azimuth12(deg)": "209.28", "azimuth21(deg)": "29.23",
    "mainant1": "77176A", "mainman1": "ANDREW", "mainmodel1": "VHLP3-11WA",
    "maindiameter1(ft)": "2.99", "maingain1(dBi)": "38.50",
    "mainbeamwidth1(3db)": "2.00", "maintilt1(deg)": "-0.10",
    "maincenline1(m)": "33.53", "maincenline1(ft)": "110.00",
    "mainant mode1": "Tx/Rx",
    "mainant2": "16995A", "mainman2": "ANDREW", "mainmodel2": "VHLP4-11WA",
    "maindiameter2(ft)": "4.00", "maingain2(dBi)": "40.80",
    "radio1": "M11AB5-2", "radioman1": "Aviat Networks, Inc.",
    "radiomodel1": "WT42O-11-80M 4096Q 1462MB", "radiomodeldesc1": "WTM 4200 ODU",
    "radio2": "M11AB5-2", "radiomodel2": "WT42O-11-80M 4096Q 1462MB",
    "stability1": "0.0005", "stability2": "0.0005",
    "nomPower1(dBm)": "15.00", "coordPower1(dBm)": "29.00", "maxPower1(dBm)": "29.00",
    "rxnomPower1(dBm)": "-44.99", "rxcoordPower1(dBm)": "-30.99", "rxmaxPower1(dBm)": "-30.99",
    "nomPower2(dBm)": "15.00", "maxPower2(dBm)": "29.00",
    "rxnomPower2(dBm)": "-44.99", "rxmaxPower2(dBm)": "-30.99",
    "maxeirp1(dBm)": "67.50", "maxeirp2(dBm)": "69.80",
    "commonLoss1(dB)": "0.00", "txLoss1(dB)": "0.00",
    "emissiondesignator1": "80M0D7W", "emissionDesignator2": "80M0D7W",
    "maxmodulation1": "4096 QAM", "minmodulation1": "QPSK",
    "maxdatarate1(kbps)": "1462000.00", "mindatarate1(kbps)": "207000.00",
    "maxmodulation2": "4096 QAM", "minmodulation2": "QPSK",
    "maxdatarate2(kbps)": "1462000.00", "mindatarate2(kbps)": "207000.00",
    "freq1_1": "11325.0", "pol1_1": "Both V/H",
    "freq2_1": "10835.0", "pol2_1": "Both V/H",
}


def make_csv(rows):
    fieldnames = list(BASE_ROW.keys())
    # Allow rows to add columns not in BASE_ROW (e.g. freq1_2 for carrier count).
    for r in rows:
        for k in r:
            if k not in fieldnames:
                fieldnames.append(k)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return io.BytesIO(buf.getvalue().encode("utf-8"))


class NormalizerTests(TestCase):
    def test_band(self):
        self.assertEqual(normalize_band("11 GHz (10700-11700 MHz) US"), "11 GHz")
        self.assertEqual(normalize_band("18 GHz (17700-19700 MHz) US"), "18 GHz")
        self.assertEqual(normalize_band("6.1 GHz (5925-6425 MHz) US"), "6 GHz")
        self.assertEqual(normalize_band("6.7 GHz (6525-6875 MHz) US"), "6 GHz")
        self.assertEqual(normalize_band(""), "")
        self.assertEqual(normalize_band("garbage"), "")

    def test_modulation(self):
        self.assertEqual(normalize_modulation("4096 QAM"), "4096 QAM")
        self.assertEqual(normalize_modulation("OFDM 1024QA"), "1024 QAM")
        self.assertEqual(normalize_modulation("OFDM 256QAM"), "256 QAM")
        self.assertEqual(normalize_modulation("OFDM QPSK"), "QPSK")
        self.assertEqual(normalize_modulation("4 QAM"), "QPSK")
        self.assertEqual(normalize_modulation("QPSK"), "QPSK")
        self.assertIsNone(normalize_modulation(""))
        self.assertIsNone(normalize_modulation("99999 QAM"))

    def test_dms(self):
        self.assertEqual(dms_to_decimal("33 10 52.86 N"), Decimal("33.181350"))
        self.assertEqual(dms_to_decimal("99 22 55.02 W"), Decimal("-99.381950"))
        self.assertIsNone(dms_to_decimal(""))

    def test_rollup_license_status(self):
        self.assertEqual(rollup_license_status("licensed", "licensed"), "licensed")
        # Worse / in-progress status wins the link headline.
        self.assertEqual(rollup_license_status("licensed", "applied"), "applied")
        self.assertEqual(rollup_license_status("licensed", "expired_terminated"), "expired_terminated")
        self.assertEqual(rollup_license_status("", ""), "")
        self.assertEqual(rollup_license_status("licensed", ""), "licensed")

    def test_misc(self):
        self.assertEqual(clean_excel('="260623C5"'), "260623C5")
        self.assertEqual(clean_excel("260623C5"), "260623C5")
        self.assertEqual(to_decimal("1,462,000.00"), Decimal("1462000.00"))
        self.assertIsNone(to_decimal(""))
        self.assertEqual(to_int("207000.00"), 207000)


class ComsearchAdapterTests(TestCase):
    def setUp(self):
        self.source = ComsearchCSVSource()

    def _one(self, row):
        return list(self.source.iter_links(make_csv([row])))[0]

    def test_profile_and_endpoints_mapped(self):
        link = self._one(dict(BASE_ROW))
        prof = link.data["profile"]
        self.assertEqual(prof["frequency_band"], "11 GHz")
        self.assertEqual(prof["rcn_number"], "260623C5")
        self.assertEqual(prof["licensee"], "AMG Technology Investment Group LLC")
        self.assertEqual(prof["path_length_km"], Decimal("18.927"))
        self.assertEqual(prof["carrier_count"], 1)

        eps = {e["side"]: e for e in link.data["endpoints"]}
        self.assertEqual(eps["A"]["pcn_site_name"], "TX-THROCKMORTON-WE-2")
        self.assertEqual(eps["A"]["latitude"], Decimal("33.181350"))
        self.assertEqual(eps["A"]["longitude"], Decimal("-99.381950"))
        self.assertEqual(eps["A"]["antenna_code"], "77176A")
        self.assertEqual(eps["A"]["path_azimuth_deg"], Decimal("209.28"))
        self.assertEqual(eps["Z"]["path_azimuth_deg"], Decimal("29.23"))
        self.assertEqual(eps["A"]["county_state"], "Throckmorton County, TX")

    def test_targets_per_direction_distinct(self):
        link = self._one(dict(BASE_ROW))
        targets = link.data["modulation_targets"]
        idents = {(t["direction"], t["modulation"]) for t in targets}
        self.assertIn(("A_TO_Z", "4096 QAM"), idents)
        self.assertIn(("A_TO_Z", "QPSK"), idents)
        self.assertIn(("Z_TO_A", "4096 QAM"), idents)
        # No duplicate (direction, modulation) pairs.
        self.assertEqual(len(idents), len(targets))

    def test_per_side_license_fields_mapped(self):
        link = self._one(dict(BASE_ROW))
        eps = {e["side"]: e for e in link.data["endpoints"]}
        self.assertEqual(eps["A"]["license_status"], "proposed")
        self.assertEqual(eps["Z"]["license_status"], "licensed")
        self.assertEqual(eps["A"]["license_basis"], "primary")
        self.assertEqual(eps["A"]["conditional_authorization"], False)
        self.assertEqual(str(eps["A"]["license_expiration_date"]), "2030-06-23")
        self.assertEqual(str(eps["Z"]["license_expiration_date"]), "2029-12-17")

    def test_link_status_rolls_up_to_attention_status(self):
        # A=Proposed, Z=Licensed -> the in-progress (Proposed) status wins.
        link = self._one(dict(BASE_ROW))
        self.assertEqual(link.data["profile"]["registration_status"], "proposed")

    def test_carrier_count_counts_freq_pairs(self):
        row = dict(BASE_ROW, **{"freq1_2": "11405.0"})
        link = self._one(row)
        self.assertEqual(link.data["profile"]["carrier_count"], 2)

    def test_key_is_order_independent_and_stable(self):
        link1 = self._one(dict(BASE_ROW))
        swapped = dict(BASE_ROW)
        swapped["site1"], swapped["site2"] = BASE_ROW["site2"], BASE_ROW["site1"]
        link2 = self._one(swapped)
        self.assertEqual(link1.key, link2.key)  # unordered site pair

    def test_distinct_links_get_distinct_keys(self):
        other = dict(BASE_ROW, **{"site2": "TX-SOMEWHERE-EL-1", "freq1_1": "11500.0"})
        self.assertNotEqual(self._one(dict(BASE_ROW)).key, self._one(other).key)


class EngineIdempotencyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        cls.ctype = CircuitType.objects.create(name="Microwave", slug="microwave")

    def _run(self, rows):
        return run_import(
            get_source("comsearch"), make_csv(rows),
            provider=self.provider, circuit_type=self.ctype,
        )

    def test_first_import_creates_then_reimport_is_idempotent(self):
        report1 = self._run([dict(BASE_ROW)])
        self.assertEqual(len(report1["created"]), 1)
        self.assertEqual(WirelessLicenseProfile.objects.count(), 1)

        profile = WirelessLicenseProfile.objects.get()
        self.assertEqual(profile.import_source, "comsearch")
        self.assertTrue(profile.import_key)
        self.assertEqual(profile.endpoints.count(), 2)

        # Re-upload the identical file: no new circuits, nothing reported changed.
        report2 = self._run([dict(BASE_ROW)])
        self.assertEqual(len(report2["created"]), 0)
        self.assertEqual(report2["unchanged"], 1)
        self.assertEqual(len(report2["changed"]), 0)
        self.assertEqual(WirelessLicenseProfile.objects.count(), 1)

    def test_changed_value_is_reported_not_written(self):
        self._run([dict(BASE_ROW)])
        before = WirelessLicenseProfile.objects.get()
        before_band = before.frequency_band

        changed_row = dict(BASE_ROW, **{"maxPower1(dBm)": "27.00"})
        report = self._run([changed_row])
        self.assertEqual(len(report["created"]), 0)
        self.assertEqual(len(report["changed"]), 1)
        fields = {c["field"] for c in report["changed"][0]["changes"]}
        self.assertTrue(
            {"maximum_power_dbm", "max_power_dbm"} & fields,
            f"expected a power field in {fields}",
        )
        # Report-only policy: the stored value is untouched.
        after = WirelessLicenseProfile.objects.get()
        ep_a = after.endpoints.get(side="A")
        self.assertEqual(ep_a.maximum_power_dbm, Decimal("29.000"))
        self.assertEqual(after.frequency_band, before_band)

    def test_license_status_and_expiration_persisted(self):
        self._run([dict(BASE_ROW)])
        profile = WirelessLicenseProfile.objects.get()
        # Link-level rollup + mixed flag (A Proposed / Z Licensed).
        self.assertEqual(profile.registration_status, "proposed")
        self.assertTrue(profile.license_status_mixed)
        # Earliest of the two ends' expirations drives renewal tracking.
        self.assertEqual(profile.license_expiration, date(2029, 12, 17))
        ep_a = profile.endpoints.get(side="A")
        self.assertEqual(ep_a.license_status, "proposed")
        self.assertEqual(ep_a.license_basis, "primary")
        self.assertEqual(ep_a.license_expiration_date, date(2030, 6, 23))

    def test_circuit_type_defaults_to_source_default(self):
        # No circuit_type passed -> source default "Licensed Microwave" get-or-created.
        run_import(
            get_source("comsearch"), make_csv([dict(BASE_ROW)]),
            provider=self.provider, circuit_type=None,
        )
        circuit = Circuit.objects.get()
        self.assertEqual(circuit.type.name, "Licensed Microwave")

    def test_circuit_status_derived_from_license_status(self):
        # BASE_ROW rolls up to "proposed" -> operational status "planned" (seeded).
        self._run([dict(BASE_ROW)])
        self.assertEqual(Circuit.objects.get().status, "planned")

    def test_status_map_is_operator_configurable(self):
        # Operator remaps "proposed" -> "offline"; the import must honor it.
        WirelessImportStatusMap.objects.update_or_create(
            license_status="proposed",
            defaults={"circuit_status": "offline", "enabled": True},
        )
        self._run([dict(BASE_ROW)])
        self.assertEqual(Circuit.objects.get().status, "offline")

    def test_disabled_status_map_falls_back_to_default(self):
        # Disabling the matching row falls back to the form's default status.
        WirelessImportStatusMap.objects.update_or_create(
            license_status="proposed",
            defaults={"circuit_status": "offline", "enabled": False},
        )
        self._run([dict(BASE_ROW)])  # _run passes no status -> default "active"
        self.assertEqual(Circuit.objects.get().status, "active")

    def test_endpoint_site_matched_and_termination_created(self):
        from circuits.models import CircuitTermination
        from dcim.models import Site

        # site1 = "TX-THROCKMORTON-WE-2" (side A); NetBox site differs only by
        # punctuation/spacing to exercise the normalized match.
        site = Site.objects.create(name="TXTHROCKMORTONWE2", slug="txthrockmortonwe2")
        self._run([dict(BASE_ROW)])
        profile = WirelessLicenseProfile.objects.get()
        ep_a = profile.endpoints.get(side="A")
        self.assertEqual(ep_a.netbox_site, site)
        ct = CircuitTermination.objects.get(circuit=profile.circuit, term_side="A")
        self.assertEqual(ct._site, site)

    def test_unmatched_site_left_blank(self):
        # No matching NetBox site -> endpoint stays unlinked, no termination.
        from circuits.models import CircuitTermination

        self._run([dict(BASE_ROW)])
        profile = WirelessLicenseProfile.objects.get()
        self.assertIsNone(profile.endpoints.get(side="A").netbox_site)
        self.assertFalse(
            CircuitTermination.objects.filter(circuit=profile.circuit).exists()
        )

    def test_two_distinct_links_create_two_circuits(self):
        row2 = dict(BASE_ROW, **{
            "site1": "MN-WINDOM-SW-1", "site2": "MN-OKABENA-SW-1",
            "rcn": '="260623C7"', "freq1_1": "11075.0",
        })
        report = self._run([dict(BASE_ROW), row2])
        self.assertEqual(len(report["created"]), 2)
        self.assertEqual(Circuit.objects.count(), 2)
