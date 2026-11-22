import Foundation
import Capacitor
import HealthKit

// Weigh-ins from Apple Health, read only (shell 1.6). The page asks for it as
// "HealthWeight" after shellHas("HealthWeight"), so older shells are never
// asked. See docs/food.md (Weigh-ins from Apple Health) and docs/ios.md.
//
// It reads one thing, body weight, the way a smart scale or the Health app
// records it, and never writes to Health: like steps, the permission has
// nothing to share. The numbers go to the page, which keeps them in the log
// on the phone; nothing here sends anything anywhere.
//
// A plugin of its own rather than more methods on HealthSteps, so that a
// page can tell a shell that has it (shellHas) from one that does not. A
// call to a method an older shell lacks would never be answered.
@objc(HealthWeightPlugin)
public class HealthWeightPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "HealthWeightPlugin"
    public let jsName = "HealthWeight"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "status", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "connect", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "days", returnType: CAPPluginReturnPromise)
    ]

    private let health = HKHealthStore()
    private let weight = HKQuantityType(.bodyMass)
    // The page's day keys: the phone's own calendar date, 2026-11-09.
    private let dayKey: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone.current
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
    private let maxDays = 400

    // Whether this phone has Health, and whether the question has been put.
    // Not the answer: iOS keeps that to itself for reading.
    @objc func status(_ call: CAPPluginCall) {
        guard HKHealthStore.isHealthDataAvailable() else {
            call.resolve(["available": false, "asked": false])
            return
        }
        health.getRequestStatusForAuthorization(toShare: [], read: [weight]) { status, _ in
            call.resolve(["available": true, "asked": status == .unnecessary])
        }
    }

    // iOS's own sheet, asking to read weight. It shows once; after that iOS
    // answers at once and the switch lives in Settings → Health.
    @objc func connect(_ call: CAPPluginCall) {
        guard HKHealthStore.isHealthDataAvailable() else {
            call.reject("Apple Health is not on this device", "unavailable")
            return
        }
        health.requestAuthorization(toShare: [], read: [weight]) { done, error in
            if let error = error {
                call.reject(error.localizedDescription, "failed", error)
                return
            }
            call.resolve(["asked": done])
        }
    }

    // Each day's weight from `from` to `to` (both "yyyy-MM-dd", the phone's own
    // days), in pounds to a tenth: the last one recorded that day, because a
    // morning weigh-in is the one the app asks for and a second step on the
    // scale is usually the correction. Days with none are left out.
    @objc func days(_ call: CAPPluginCall) {
        guard HKHealthStore.isHealthDataAvailable() else {
            call.reject("Apple Health is not on this device", "unavailable")
            return
        }
        let cal = Calendar.current
        guard let from = dayKey.date(from: call.getString("from") ?? ""),
              let to = dayKey.date(from: call.getString("to") ?? ""),
              from <= to,
              let span = cal.dateComponents([.day], from: from, to: to).day, span <= maxDays,
              let end = cal.date(byAdding: .day, value: 1, to: to) else {
            call.reject("from and to must be days, from first, at most \(maxDays) apart", "bad_range")
            return
        }
        let query = HKSampleQuery(
            sampleType: weight,
            predicate: HKQuery.predicateForSamples(withStart: from, end: end, options: []),
            limit: HKObjectQueryNoLimit,
            sortDescriptors: [NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)]
        ) { [weak self] _, samples, error in
            guard let self = self else { return }
            if let error = error {
                let code = (error as? HKError)?.code
                switch code {
                case .some(.errorNoData):
                    call.resolve(["days": JSObject()])
                // Health's store is locked while the phone is: try again later.
                case .some(.errorDatabaseInaccessible):
                    call.reject("Apple Health is locked until the phone is unlocked", "locked", error)
                case .some(.errorAuthorizationNotDetermined):
                    call.reject("Apple Health has not been asked yet", "not_asked", error)
                default:
                    call.reject(error.localizedDescription, "failed", error)
                }
                return
            }
            var out = JSObject()
            for case let s as HKQuantitySample in samples ?? [] {
                let lb = (s.quantity.doubleValue(for: .pound()) * 10).rounded() / 10
                if lb > 0 { out[self.dayKey.string(from: s.startDate)] = lb }   // later ones win
            }
            call.resolve(["days": out])
        }
        health.execute(query)
    }
}
