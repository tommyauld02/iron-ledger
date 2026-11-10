import UIKit
import Capacitor

// Capacitor's own view controller, plus the plugins that live in the app
// rather than in a package. Main.storyboard names this class. Registered here,
// before the page loads, a plugin is announced to the page like any other, so
// Capacitor.isPluginAvailable() answers for it.
class MainViewController: CAPBridgeViewController {
    override func capacitorDidLoad() {
        bridge?.registerPluginInstance(HealthStepsPlugin())    // shell 1.4
    }
}
