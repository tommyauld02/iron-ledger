import UIKit
import Capacitor

class SceneDelegate: UIResponder, UIWindowSceneDelegate {
    var window: UIWindow?

    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions) {
        guard let windowScene = scene as? UIWindowScene else { return }

        window = UIWindow(windowScene: windowScene)
        window?.rootViewController = CAPBridgeViewController()
        window?.makeKeyAndVisible()

        if let item = connectionOptions.shortcutItem { noteQuickAction(item) }

        SceneDelegateProxy.shared.scene(scene, willConnectTo: session, options: connectionOptions)
    }

    func scene(_ scene: UIScene, openURLContexts URLContexts: Set<UIOpenURLContext>) {
        SceneDelegateProxy.shared.scene(scene, openURLContexts: URLContexts)
    }

    func scene(_ scene: UIScene, continue userActivity: NSUserActivity) {
        SceneDelegateProxy.shared.scene(scene, continue: userActivity)
    }

    // A quick action on the icon, with the app already running.
    func windowScene(_ windowScene: UIWindowScene, performActionFor shortcutItem: UIApplicationShortcutItem, completionHandler: @escaping (Bool) -> Void) {
        noteQuickAction(shortcutItem)
        (window?.rootViewController as? CAPBridgeViewController)?.bridge?.triggerWindowJSEvent(eventName: "mntlquickaction")
        completionHandler(true)
    }

    // Left where @capacitor/preferences reads it (its prefix, then the key), so
    // the page finds it whenever it is ready. See "quick actions" in mntl-dt.html.
    private func noteQuickAction(_ item: UIApplicationShortcutItem) {
        UserDefaults.standard.set(item.type, forKey: "CapacitorStorage.mntl-quick-action")
    }
}
