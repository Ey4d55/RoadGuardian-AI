"""Impact arithmetic, missing inputs and isolation of safety from eco assumptions."""
import unittest
from engine import evaluate
from ecotwin import impact, payload, component_html


class EcoTwinTests(unittest.TestCase):
    def test_units_and_zero(self):
        result = impact(12, 60)
        self.assertAlmostEqual(result['fuel_l'], .2)
        self.assertAlmostEqual(result['co2_kg'], .4696)
        self.assertEqual(impact(0, 60)['co2_kg'], 0)

    def test_missing_and_invalid(self):
        self.assertIsNone(impact(None, 60))
        self.assertIsNone(impact(12, None))
        for value in (-1, float('nan'), float('inf'), True, .5):
            with self.assertRaises(ValueError):
                impact(value, 60)

    def test_safety_unchanged_and_cost_increase_preserved(self):
        event = dict(truck_present=True, truck_height_m=5, cloud_online=False)
        result = evaluate(event)
        original = result.copy()
        data = payload(event, result, dict(vehicles=12, before_s=20, after_s=50,
                                          idle_lph=1, co2_kg_per_l=2.348))
        self.assertGreater(data['after']['co2_kg'], data['before']['co2_kg'])
        self.assertTrue(data['safety_locked'])
        self.assertEqual(data['action'], 'LOCAL_BRIDGE_ALERT')
        self.assertEqual(result, original)
        live = payload(event, result, data['assumptions'], simulated=False)
        self.assertIsNone(live['before'])
        self.assertIsNone(live['after'])

    def test_template_safe_embedding(self):
        data = payload({}, dict(risk=100, level='BRIDGE_CRITICAL',
                                action='</script><script>alert(1)</script>',
                                truck_present=True, truck_height_m=5))
        html = component_html(data)
        self.assertNotIn('__ECO_DATA__', html)
        self.assertNotIn('__FONT_DATA__', html)
        self.assertNotIn('</script><script>alert(1)', html)


if __name__ == '__main__':
    unittest.main()
