"""
Comsearch microwave-links CSV export adapter.

One wide row = one link. Side ``1`` -> endpoint **A**, side ``2`` -> endpoint
**Z**. The export carries no single reliable identifier (the native ``link id``
column is mostly blank and a single ``rcn`` repeats across links), so the stable
de-duplication key is the unordered **site pair + band + RCN + center frequency**,
which is unique across the full export. A re-upload matches on that key.
"""
import csv
import hashlib
import io
from datetime import datetime

from .base import (
    BaseCSVSource,
    ParsedLink,
    clean_excel,
    dms_to_decimal,
    normalize_band,
    normalize_modulation,
    register_source,
    to_decimal,
    to_int,
)

# Comsearch status1/status2 -> registration_status workflow value.
_STATUS_MAP = {
    "proposed": "submitted",
    "applied": "submitted",
    "registered": "registered",
    "granted": "granted",
    "licensed": "granted",
    "prior coordination notice": "submitted",
}


def _parse_date(value):
    s = (value or "").strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _drop_empty(d):
    return {k: v for k, v in d.items() if v not in (None, "")}


@register_source
class ComsearchCSVSource(BaseCSVSource):
    name = "comsearch"
    label = "Comsearch (microwave links export)"
    description = (
        "Comsearch CommSearch / microwave links CSV (one link per row, sides 1/2 "
        "→ endpoints A/Z). De-duplicated on site pair + band + RCN + frequency."
    )

    def iter_links(self, file_obj):
        raw = file_obj.read()
        if isinstance(raw, bytes):
            text = raw.decode("utf-8-sig", errors="replace")
        else:
            text = raw
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            link = self._parse_row(row)
            if link is not None:
                yield link

    # -- per-row mapping -----------------------------------------------------

    def _parse_row(self, r):
        g = lambda k: (r.get(k) or "").strip()  # noqa: E731

        site1, site2 = g("site1"), g("site2")
        if not site1 and not site2:
            return None  # blank / trailing row

        band = normalize_band(g("band"))
        rcn = clean_excel(r.get("rcn"))
        freq1 = g("freq1_1")
        key = self._link_key(site1, site2, band, rcn, freq1)

        profile = self._profile(r, band, rcn)
        endpoints = [
            self._endpoint(r, side="A", n="1", azimuth=g("azimuth12(deg)")),
            self._endpoint(r, side="Z", n="2", azimuth=g("azimuth21(deg)")),
        ]
        targets = self._targets(r)

        cid = self._cid(site1, site2)
        return ParsedLink(
            key=key,
            cid=cid,
            link_id=g("link id"),
            data={
                "profile": profile,
                "endpoints": endpoints,
                "modulation_targets": targets,
            },
        )

    @staticmethod
    def _link_key(site1, site2, band, rcn, freq):
        a, b = sorted([site1.strip().upper(), site2.strip().upper()])
        composite = "|".join([a, b, band, rcn, (freq or "").strip()])
        return hashlib.sha1(composite.encode("utf-8")).hexdigest()

    @staticmethod
    def _cid(site1, site2):
        a, b = sorted([site1.strip(), site2.strip()])
        return f"MW {a} ↔ {b}".strip()

    def _profile(self, r, band, rcn):
        g = lambda k: (r.get(k) or "").strip()  # noqa: E731
        status = _STATUS_MAP.get(g("status1").lower(), "")
        return _drop_empty({
            "frequency_band": band,
            "rcn_number": rcn,
            "job_number": g("job number"),
            "registration_status": status,
            "pcn_date": _parse_date(g("Current PCN Date")),
            "licensee": g("company1") or g("owner1"),
            "call_sign": g("call1"),
            "radio_service": g("radio service1"),
            "station_class": g("station class1"),
            "channel_plan_mhz": to_decimal(g("planbandwidth1(MHz)")),
            "path_length_km": to_decimal(g("distance(km)")),
            "path_length_miles": to_decimal(g("distance(mi)")),
            "atmospheric_loss_db": to_decimal(g("atmosphericLoss(dB)")),
            "free_space_loss_db": to_decimal(g("freeSpaceLoss(dB)")),
            "carrier_count": self._carrier_count(r, "1"),
        })

    @staticmethod
    def _carrier_count(r, n):
        count = sum(
            1 for i in range(1, 14) if (r.get(f"freq{n}_{i}") or "").strip()
        )
        return count or None

    def _endpoint(self, r, side, n, azimuth):
        g = lambda k: (r.get(k) or "").strip()  # noqa: E731
        county = g(f"county{n}")
        state = g(f"state{n}")
        county_state = ", ".join(p for p in (county, state) if p)
        return _drop_empty({
            "side": side,
            "pcn_site_name": g(f"site{n}"),
            "county_state": county_state,
            "latitude": dms_to_decimal(g(f"latitude{n}")),
            "longitude": dms_to_decimal(g(f"longitude{n}")),
            "ground_elevation_m": to_decimal(g(f"ground{n}(m)")),
            "ground_elevation_ft": to_decimal(g(f"ground{n}(ft)")),
            "asr_number": g(f"asr number{n}"),
            "path_azimuth_deg": to_decimal(azimuth),
            "antenna_code": g(f"mainant{n}"),
            "antenna_manufacturer": g(f"mainman{n}"),
            "antenna_model": g(f"mainmodel{n}"),
            "antenna_diameter_ft": to_decimal(g(f"maindiameter{n}(ft)")),
            "antenna_gain_dbi": to_decimal(g(f"maingain{n}(dBi)")),
            "antenna_beamwidth_deg": to_decimal(g(f"mainbeamwidth{n}(3db)")),
            "antenna_tilt_deg": to_decimal(g(f"maintilt{n}(deg)")),
            "centerline_agl_m": to_decimal(g(f"maincenline{n}(m)")),
            "centerline_agl_ft": to_decimal(g(f"maincenline{n}(ft)")),
            "transmit_mode": g(f"mainant mode{n}"),
            "radio_code": g(f"radio{n}"),
            "radio_manufacturer": g(f"radioman{n}"),
            "radio_model": g(f"radiomodel{n}"),
            "radio_description": g(f"radiomodeldesc{n}"),
            "stability_percent": to_decimal(g(f"stability{n}")),
            "nominal_power_dbm": to_decimal(g(f"nomPower{n}(dBm)")),
            "coordinated_power_dbm": to_decimal(g(f"coordPower{n}(dBm)")),
            "maximum_power_dbm": to_decimal(g(f"maxPower{n}(dBm)")),
            "nominal_rsl_dbm": to_decimal(g(f"rxnomPower{n}(dBm)")),
            "coordinated_rsl_dbm": to_decimal(g(f"rxcoordPower{n}(dBm)")),
            "maximum_rsl_dbm": to_decimal(g(f"rxmaxPower{n}(dBm)")),
            "fixed_loss_common_db": to_decimal(g(f"commonLoss{n}(dB)")),
            "fixed_loss_tx_db": to_decimal(g(f"txLoss{n}(dB)")),
            "fixed_loss_rx_db": to_decimal(g(f"rxLoss{n}(dB)")),
            "tx_frequency_mhz": to_decimal(g(f"freq{n}_1")),
            "polarization": g(f"pol{n}_1"),
        })

    def _targets(self, r):
        """
        Two directions; for each, a top (max) and bottom (min) modulation rung.
        Direction A→Z is what side 1 transmits and side 2 receives, so the
        expected RSL is the receiving side's nominal rx power. Duplicate
        (direction, modulation) pairs are dropped to satisfy the model's
        per-direction-per-modulation uniqueness.
        """
        out = []
        seen = set()
        for direction, tx, rx, emis in (
            ("A_TO_Z", "1", "2", ("emissiondesignator1", "emissionDesignator1")),
            ("Z_TO_A", "2", "1", ("emissionDesignator2", "emissiondesignator2")),
        ):
            g = lambda k: (r.get(k) or "").strip()  # noqa: E731
            emission = next((g(k) for k in emis if g(k)), "")
            rungs = (
                (g(f"maxmodulation{tx}"), g(f"maxdatarate{tx}(kbps)")),
                (g(f"minmodulation{tx}"), g(f"mindatarate{tx}(kbps)")),
            )
            for raw_mod, raw_rate in rungs:
                mod = normalize_modulation(raw_mod)
                if not mod or (direction, mod) in seen:
                    continue
                seen.add((direction, mod))
                out.append(_drop_empty({
                    "direction": direction,
                    "modulation": mod,
                    "data_rate_kbps": to_int(raw_rate),
                    "max_power_dbm": to_decimal(g(f"maxPower{tx}(dBm)")),
                    "eirp_dbm": to_decimal(g(f"maxeirp{tx}(dBm)")),
                    "expected_rsl_dbm": to_decimal(g(f"rxnomPower{rx}(dBm)")),
                    "min_acceptable_rsl_dbm": to_decimal(g(f"rxmaxPower{rx}(dBm)")),
                    "emission_designator": emission,
                    "radio_model": g(f"radiomodel{tx}"),
                }))
        return out
