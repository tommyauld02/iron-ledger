import Foundation
import Capacitor
import HealthKit

// Steps from Apple Health, read only (shell 1.4). The page asks for it as
// "HealthSteps" after shellHas("HealthSteps"), so older shells are never
// asked. See docs/cardio.md and docs/ios.md (Steps from Apple Health).
//
// It reads one thing, the step count, and never writes to Health: the
// permission asked for has nothing to share, so iOS shows a read-only
// request and the app needs no NSHealthUpdateUsageDescription. The numbers
// go to the page, which keeps them in the log on the phone; nothing here
// sends anything anywhere.
//
// iOS never tells an app whether reading was allowed. A "no" looks exactly
// like a day with no steps, so the page says where the switch is when
// Health gives it nothing at all, rather than claiming either.
@objc(HealthStepsPlugin)
public class HealthStepsPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "HealthStepsPlugin"
    public let jsName = "HealthSteps"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "status", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "connect", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "days", returnType: CAPPluginReturnPromise)
    ]

    private let health = HKHealthStore()
    private let steps = HKQuantityType(.stepCount)
    // The page's day keys: the phone's own calendar date, 2026-11-09.
    private let dayKey: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone.current
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
    // The longest stretch read at once: a little over the Log's eight months.
    private let maxDays = 400

    // Whether this phone has Health (every iPhone does), and whether the
    // question has been put to the person already. Not the answer: iOS keeps
    // that to itself for reading.
    @objc func status(_ call: CAPPluginCall) {
        guard HKHealthStore.isHealthDataAvailable() else {
            call.resolve(["available": false, "asked": false])
            return
        }
        health.getRequestStatusForAuthorization(toShare: [], read: [steps]) { status, _ in
            call.resolve(["available": true, "asked": status == .unnecessary])
        }
    }

    // iOS's own sheet, asking to read steps. It shows once; after that iOS
    // answers at once and the switch lives in Settings → Health.
    @objc func connect(_ call: CAPPluginCall) {
        guard HKHealthStore.isHealthDataAvailable() else {
            call.reject("Apple Health is not on this device", "unavailable")
            return
        }
        health.requestAuthorization(toShare: [], read: [steps]) { done, error in
            if let error = error {
                call.reject(error.localizedDescription, "failed", error)
                return
            }
            call.resolve(["asked": done])
        }
    }

    // Each day's steps from `from` to `to` (both "yyyy-MM-dd", the phone's own
    // days), as Health adds them up: an iPhone and a watch counting the same
    // walk count it once, the way the Health app shows it. Days with no
    // steps are left out.
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
        let query = HKStatisticsCollectionQuery(
            quantityType: steps,
            quantitySamplePredicate: HKQuery.predicateForSamples(withStart: from, end: end, options: []),
            options: .cumulativeSum,
            anchorDate: cal.startOfDay(for: from),
            intervalComponents: DateComponents(day: 1))
        query.initialResultsHandler = { [weak self] _, results, error in
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
            results?.enumerateStatistics(from: from, to: to) { day, _ in
                guard let sum = day.sumQuantity() else { return }
                let n = Int(sum.doubleValue(for: .count()).rounded())
                if n > 0 { out[self.dayKey.string(from: day.startDate)] = n }
            }
            call.resolve(["days": out])
        }
        health.execute(query)
    }
}
