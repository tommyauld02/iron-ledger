import UIKit
import Capacitor

// Tells the WebView that a keyboard it still thinks is up has gone (shell 1.5).
// The page asks for it as "KeyboardReset" after shellHas("KeyboardReset"), so
// older shells are never asked. See docs/ui.md (*A keyboard the WebView
// still thinks is up*) and docs/ios.md (The keyboard reset).
//
// The WebView learns where the keyboard is only from iOS's keyboard
// notifications. Now and then it misses the one saying the keyboard went, and
// goes on keeping a keyboard's height at the foot of the screen for one that
// is not there: the visual viewport stays 336 points short, and the tab bar,
// which sits at the foot of the page's viewport, rides halfway up the screen
// as you scroll (the owner's video, b101, the TestFlight app). It lasts until
// the next keyboard comes and goes. Nothing the page can do reaches it.
//
// reset() sends the WebView the notification it missed: the keyboard is off
// the bottom of the screen, at once, with no animation. It is iOS's own
// public notification with iOS's own keys, the same one the WebView heard
// when a real keyboard went. The page calls it only when nothing on it is
// taking typing, which is the only time an iPhone shows the WebView's
// keyboard; a real keyboard's next notification would put the WebView right
// in any case.
@objc(KeyboardResetPlugin)
public class KeyboardResetPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "KeyboardResetPlugin"
    public let jsName = "KeyboardReset"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "reset", returnType: CAPPluginReturnPromise)
    ]

    @objc func reset(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            let screen = self.bridge?.webView?.window?.windowScene?.screen.bounds
                ?? self.bridge?.webView?.bounds ?? .zero
            // Below the screen: what the WebView takes from it is nothing.
            let gone = CGRect(x: 0, y: screen.height, width: screen.width, height: 336)
            let info: [AnyHashable: Any] = [
                UIResponder.keyboardFrameBeginUserInfoKey: NSValue(cgRect: gone),
                UIResponder.keyboardFrameEndUserInfoKey: NSValue(cgRect: gone),
                UIResponder.keyboardAnimationDurationUserInfoKey: 0.0,
                UIResponder.keyboardAnimationCurveUserInfoKey: UIView.AnimationCurve.easeInOut.rawValue,
                UIResponder.keyboardIsLocalUserInfoKey: true
            ]
            let nc = NotificationCenter.default
            nc.post(name: UIResponder.keyboardWillHideNotification, object: nil, userInfo: info)
            nc.post(name: UIResponder.keyboardDidChangeFrameNotification, object: nil, userInfo: info)
            call.resolve()
        }
    }
}
