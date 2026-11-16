"""Regression checks for packet-ready signaling and bounded idle shutdown."""
import sys,time,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'lib'))
from native_wasapi import AudioReadyEvent

class AudioEventTests(unittest.TestCase):
    def test_signal_wakes_waiter_and_auto_resets(self):
        event=AudioReadyEvent();entered=threading.Event();results=[]
        def wait():
            entered.set();results.append(event.wait(1000))
        thread=threading.Thread(target=wait)
        try:
            thread.start();self.assertTrue(entered.wait(1))
            event.kernel.SetEvent(event.handle)
            thread.join(timeout=.5)
            self.assertFalse(thread.is_alive());self.assertEqual(results,[True])
            self.assertFalse(event.wait(0))
        finally:thread.join(timeout=2);event.close()
    def test_preexisting_signal_is_not_lost(self):
        event=AudioReadyEvent()
        try:
            event.kernel.SetEvent(event.handle)
            self.assertTrue(event.wait(0));self.assertFalse(event.wait(0))
        finally:event.close()
    def test_idle_wait_is_bounded_and_close_idempotent(self):
        event=AudioReadyEvent()
        try:
            start=time.perf_counter();self.assertFalse(event.wait())
            self.assertLess(time.perf_counter()-start,.5)
        finally:event.close();event.close()

if __name__=='__main__':unittest.main()
