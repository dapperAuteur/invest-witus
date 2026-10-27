> Copied 2026-10-27 from the WitUS ecosystem's local planning notes, `gemini/witus/plans/future/invest-witus-research-2026-10-27/03-law-and-vendor-terms.md` (researched and written 2026-10-27). Edit on copy: one personal reference generalized to "the operator". Paths to `plans/` files refer to those local notes and are not in this repo.

# Invest.WitUS research 03: law, rules and vendor terms

Researched: October 27, 2026

Scope: the law-and-rules slice of the Invest.WitUS vetting analysis (gates G4 and G6, dimension D9 of `docs/app-idea-vetting-rubric.md`). The seed note is `plans/future/python-investing-app-seed-2026-10-27.md`.

Two slices are judged throughout:

- **First slice:** BAM's own money and BAM's own Alpaca paper account, a public waitlist, no other users, no fee.
- **Later slice:** other users, possibly students, connecting their own accounts (Alpaca or SnapTrade), with the app showing a method's signals or placing orders.

Evidence tags: **V** means the text was fetched and read today (October 27, 2026) and is quoted. **I** means inferred from V facts, with the reasoning shown. Nothing here is legal advice. Where a fact pattern might or might not fall inside a rule, this file says so and lists it under "Open questions for a lawyer".

A note on currency: the U.S. Code text used is the govinfo "United States Code, 2024 Edition". The eCFR text came from the eCFR versioner API, which reported titles 16 and 17 "up to date as of" 2026-10-23. The Indiana Code text is the General Assembly's "Indiana Code 2026" PDF.

---

## 1. When does software that picks or signals trades for other people make its operator an "investment adviser"?

**Plain answer.** The federal definition turns on four things: compensation, being "in the business", advising **others**, and the subject being securities (or issuing analyses or reports about securities "as part of a regular business"). A tool that runs only on its owner's money advises nobody else. A tool that tells other people what to buy or sell, or buys and sells for them, and earns money for it, sits close to the center of the definition. SEC staff guidance treats automated advisers ("robo-advisers") as registered investment advisers subject to the Act's fiduciary duties. Small advisers register with their home state, not the SEC. Indiana requires registration unless an exemption or exclusion applies, plus at least one registered investment adviser representative who has passed the Series 65 (or Series 66 plus a FINRA exam).

### 1.1 The federal definition (V)

Investment Advisers Act of 1940, section 202(a)(11), 15 U.S.C. 80b-2(a)(11) (govinfo, U.S. Code 2024 edition):

> "'Investment adviser' means any person who, for compensation, engages in the business of advising others, either directly or through publications or writings, as to the value of securities or as to the advisability of investing in, purchasing, or selling securities, or who, for compensation and as part of a regular business, issues or promulgates analyses or reports concerning securities; but does not include ..."

The exclusions that matter here (same paragraph):

> "(B) any lawyer, accountant, engineer, or teacher whose performance of such services is solely incidental to the practice of his profession;"

> "(C) any broker or dealer whose performance of such services is solely incidental to the conduct of his business as a broker or dealer and who receives no special compensation therefor;"

> "(D) the publisher of any bona fide newspaper, news magazine or business or financial publication of general and regular circulation;"

> "(H) such other persons not within the intent of this paragraph, as the Commission may designate by rules and regulations or order."

The same section also defines a related term, at 202(a)(13): "'Investment supervisory services' means the giving of continuous advice as to the investment of funds on the basis of the individual needs of each client." (V)

### 1.2 SEC staff guidance on robo-advisers (V)

SEC Division of Investment Management, *IM Guidance Update No. 2017-02, Robo-Advisers* (February 2017), page 1:

> "Robo-advisers, which are typically registered investment advisers, use innovative technologies to provide discretionary asset management services to their clients through online algorithmic-based programs."

Page 2:

> "Robo-advisers, like all registered investment advisers, are subject to the substantive and fiduciary obligations of the Advisers Act."

Page 2 names three areas of concern: "The substance and presentation of disclosures to clients about the robo-adviser and the investment advisory services it offers"; "The obligation to obtain information from clients to support the robo-adviser's duty to provide suitable advice"; and "The adoption and implementation of effective compliance programs reasonably designed to address particular concerns relevant to providing automated advice."

(The sec.gov PDF downloaded; its text was extracted locally because the fetch tool could not read the compressed PDF.)

### 1.3 Federal versus state registration (V)

15 U.S.C. 80b-3a(a)(1) (section 203A): an adviser "regulated or required to be regulated as an investment adviser in the State in which it maintains its principal office and place of business" may not register with the SEC "unless the investment adviser ... (A) has assets under management of not less than $25,000,000, or such higher amount as the Commission may, by rule, deem appropriate ..." or advises a registered investment company.

15 U.S.C. 80b-3a(a)(2) covers "mid-sized" advisers: state-registered and state-examined advisers with assets under management between the paragraph (1) amount and "$100,000,000, or such higher amount as the Commission may, by rule, deem appropriate". They do not register with the SEC unless they advise a registered fund or would have to register with 15 or more states.

15 U.S.C. 80b-3a(a)(3): "'assets under management' means the securities portfolios with respect to which an investment adviser provides continuous and regular supervisory or management services."

SEC Rule 203A-1(a)(1), 17 CFR 275.203A-1 (eCFR): "You may, but are not required to register with the Commission if you have assets under management of at least $100,000,000 but less than $110,000,000, and you need not withdraw your registration unless you have less than $90,000,000 of assets under management."

15 U.S.C. 80b-3a(b)(1)(B) preempts state registration for a person "that is not registered under section 80b-3 of this title because that person is excepted from the definition of an investment adviser under section 80b-2(a)(11)".

### 1.4 Indiana (V)

Indiana Securities Division, investment adviser general information page (securities.sos.in.gov; the old in.gov URL redirects there):

> "Investment advisers conducting business or with a place of business in Indiana must register"

> "An investment adviser may register with the SEC once it has one hundred million dollars ($100,000,000) in AUM."

> "When the investment adviser reaches one hundred and ten million dollars ($110,000,000) in AUM, the investment adviser is required to register with the SEC."

> "The non-refundable initial filing fee is one hundred dollars ($100) and is paid through FINRA."

> "Each investment adviser must have at least one investment adviser representative registered with the investment adviser."

> "An investment adviser representative must pass either the Uniform Investment Adviser Law Examination (Series 65);" or "the applicable required FINRA examination(s) and the Uniform Combined State Law Examination (Series 66)."

The page also says Form ADV Parts 1 and 2 are filed through IARD, and that if a person is excluded from the definition under IC 23-19-1-2(15) "then registration is not required."

Indiana Code 23-19-1-2(15) (Indiana Code 2026 PDF) copies the federal definition and adds:

> "The term includes a financial planner or other person that, as an integral component of other financially related services, provides investment advice to others for compensation as part of a business or that holds itself out as providing investment advice to others for compensation."

Its exclusions include "(B) a lawyer, accountant, engineer, or teacher whose performance of investment advice is solely incidental to the practice of the person's profession;", "(D) a publisher of a bona fide newspaper, news magazine, or business or financial publication of general and regular circulation;", "(E) a federal covered investment adviser;" and "(G) any other person that is excluded by the Investment Advisers Act of 1940 from the definition of investment adviser;".

IC 23-19-4-3(a): "It is unlawful for a person to transact business in this state as an investment adviser unless the person is registered under this article as an investment adviser or is exempt from registration as an investment adviser under subsection (b)." The exemptions in (b) are for a person **without a place of business in Indiana** (institutional or adviser-only clients, or "not more than five (5) clients that are resident in this state" in the past twelve months) or a person exempted by rule or order. (V)

### 1.5 What it means

- **First slice (own money, paper, waitlist): I.** The definition requires "advising others" and "compensation". Running the app on BAM's own paper account advises no one else and earns nothing. The text does not reach it. Tag I, because the reasoning applies the statute's words to the facts; no source addresses this exact case.
- **Later slice (other users): I.** If the app tells identified users which securities to buy or sell, or places those orders, and anyone pays (a subscription, a tier, or possibly something less direct), the activity matches the words "for compensation, engages in the business of advising others ... as to the advisability of ... purchasing, or selling securities." The operator's principal place of business is in Indiana, so the 203A split would point at Indiana registration (with Series 65 and Form ADV) long before any SEC threshold. Whether a free app, a donation model, or an app that only signals but never trades falls inside the definition is a question for a securities lawyer. The fetched sources do not define "compensation".
- **Students (I).** IC 23-19-1-2(15)(B) and 202(a)(11)(B) exclude a teacher only where the advice is "solely incidental to the practice of" the profession. An app that signals trades on a student's real account is not obviously incidental to teaching. That is a lawyer's question.

---

## 2. What may a person do without registering?

**Plain answer.** Three things are outside the words or inside an exclusion on the face of the text: running a tool on one's own money (not "others"); bona fide publications of general and regular circulation (the publisher exclusion); and teaching where any advice is solely incidental to teaching. In *Lowe v. SEC* (1985), the Supreme Court held that newsletters giving impersonal advice to the general public on a regular schedule fell inside the publisher exclusion. A "model portfolio" or a list of signals published to everyone on a fixed schedule resembles the *Lowe* newsletters. An app that applies signals to a user's own account, or places trades in it, resembles individualized advice. Where the line falls is a question for a securities lawyer.

### 2.1 The publisher exclusion (V)

15 U.S.C. 80b-2(a)(11)(D): the definition "does not include ... (D) the publisher of any bona fide newspaper, news magazine or business or financial publication of general and regular circulation;". Indiana's IC 23-19-1-2(15)(D) is the same in substance. (V)

### 2.2 Lowe v. SEC, 472 U.S. 181 (1985) (V)

Fetched from the Cornell Legal Information Institute copy of the opinion and syllabus (decided June 10, 1985). Syllabus:

> "Petitioners' publications fall within the statutory exclusion for bona fide publications, ... none of the petitioners is an 'investment adviser' as defined in the Act"

> "The mere fact that a publication contains advice and comment about specific securities does not give it the personalized character that identifies a professional investment adviser."

> "Thus, petitioners' newsletters do not fit within the Act's central purpose because they do not offer individualized advice attuned to any specific portfolio or to any client's particular needs."

> "Because the content of petitioners' newsletters was completely disinterested, and because they were offered to the general public on a regular schedule, they are described by the plain language of § 202(a)(11)(D)'s exclusion."

> "In light of the legislative history, the term 'bona fide' translates best to 'genuine'."

### 2.3 What it means

| Activity | What the text says | Tag |
|---|---|---|
| Run the method on BAM's own paper or real account | Definition needs "advising others" for "compensation"; neither is present | I |
| Publish general education (lessons on momentum, rebalancing, the wash-sale rule) in Learn.WitUS or ElementaryMBA | Teaching that does not tell anyone what to buy is not advice "as to the advisability of ... purchasing, or selling securities"; the teacher exclusion (B) covers advice "solely incidental" to teaching | I |
| Publish the same model portfolio or signal list to everyone, on a regular schedule, with no tailoring | Resembles the *Lowe* newsletters, which were "offered to the general public on a regular schedule" and "completely disinterested" | I; lawyer to confirm |
| Show a user signals computed **on that user's own holdings**, or rebalance that user's account | Looks like "individualized advice attuned to any specific portfolio", which *Lowe* says the exclusion does not cover | I; lawyer to confirm |
| Place orders in a user's account automatically | Matches what the SEC staff guidance calls "discretionary asset management services" by robo-advisers, "typically registered investment advisers" | I; lawyer to confirm |

The product idea in the seed ("the app helps the user stay with that method", picking the method and its rules) sits between rows 3 and 4. A design that publishes each method's rules and signals to all users the same way, and leaves the decision and the order to the user, is closer to row 3. A design that computes "you hold X, sell it" for one account is closer to row 4. The difference is a question for a securities lawyer, and the design choice should be made with that lawyer.

---

## 3. Does giving the app power to place trades on a user's account change anything?

**Plain answer.** Yes, on both sides: the law and the vendor contracts. Alpaca's customer agreement makes each account "self-directed" and requires Alpaca's approval before any other person trades for the account. Alpaca's Trading API serves customers who "self-direct their own investments"; its Broker API is the product for apps that serve end users, listed for broker-dealers and RIAs. SnapTrade's free plan is for "testing and personal use only", one connected user. SnapTrade's compliance policy allows automated orders only when "rules-based and non-stochastic", and refuses anything that looks like "a blanket grant of trading authority" unless the app is registered. "Fully managed services" need a registered investment adviser.

### 3.1 Alpaca (V)

Alpaca Customer Agreement (version marker V26.2026.07, downloaded from files.alpaca.markets):

- Section 4: "I understand that My Account is self-directed." and "My use or My grant of access to My Account to any third party to access information or place transactions in My Account is solely at My risk."
- Section 5(a): "I am solely responsible for any and all orders placed in My Account and all orders entered by me or on My behalf are unsolicited and based on My own investment decisions or the investment decision of My duly authorized representative or agent." Alpaca does not "provide investment advice", "recommend any security, transaction or order", or "make discretionary trades".
- Section 5(c): "In the event that I wish to grant a third-party power and authority over My Account, I will complete a Limited Power of Attorney and Hold Harmless Agreement ('POA') and submit the executed POA to You."
- Section 10: "I further agree not to allow any person to trade for My Account unless a trading authorization for that person has been received and approved by Alpaca."
- Section 49: "Alpaca provides no investment, legal or tax advice."

Alpaca Disclosures page: "Brokerage services are provided by Alpaca Clearing, member FINRA/SIPC, a wholly-owned subsidiary of AlpacaDB, Inc."; brokerage services go to customers "who can write automated investment code and self-direct their own investments"; "The Paper Trading API is offered by AlpacaDB, Inc. and does not require real money". (V)

Alpaca Terms and Conditions: "Alpaca Securities provides self-directed investors with discount brokerage services, and does not make recommendations of any kind." (V)

Alpaca paper trading docs: "Anyone globally can create an Alpaca Paper Only Account!" and "Your initial paper trading account is created with $100k balance as a default setting." Paper trading "is only a simulation", and "Paper trading account **does NOT** simulate dividends." (V)

Alpaca Broker API docs ("About Broker API"): use cases are "Broker dealer (fully-disclosed, omnibus)" and "Registered Investment Advisor (RIA)"; the API is for those who "build trading apps and brokerage services for your end users". The Broker API product page lists "investment advisers" and "fintech startups" among users and says "Non-registered technology partners can leverage Alpaca's KYC as a service to get to market faster." Neither page says which registrations each setup requires. (V)

The Trading API docs page does not say who may use it; it says only that Alpaca "offers live brokerage accounts (with real money) for individuals and businesses". (V)

### 3.2 SnapTrade (V)

Pricing page: Build is "$0", "Up to 5 brokerage connections", "For developing and testing your integration." Launch is "$100 / month" plus per-user pricing, "For commercial apps getting off the ground"; real-time users cost "$2 per connected user / month"; the Daily option is marked "Trading not included" and "read only". (V)

Developer Terms of Use ("Last Updated: May 22, 2026"):

- "Client may use the Free Plan for testing and personal use only."
- The Free Plan is "for a single Connected User with up to five (5) brokerage connections", and each person or entity is "limited to one Free Plan."
- "Client may use the Pay-as-You-Go Plan for testing, personal and commercial use."
- "The Client's use of the SnapTrade API is at the Client's sole risk." Liability is capped at the greater of $100 or fees paid in the prior 12 months.
- "CLIENT IS SOLELY RESPONSIBLE FOR ITS END USERS' USE OF THE SERVICE."
- Each End User "utilizing the Client Application to access his or her account data and/or execute trades" must have authorized the Client; the Client must "require all End Users to agree to SnapTrade's End User Terms and Conditions".
- "The Client Application is operated in compliance with all applicable laws".
- "The Client agrees to notify SnapTrade within 24 hours of any breach of the Client's systems or applications."

SnapTrade docs, "Personal vs Commercial": Personal is "An individual using SnapTrade for their own brokerage accounts." Commercial is "A company building an app for its own end users." "Personal users are currently completely free." "Commercial customers start with a test key and can create production keys after KYC approval." (V)

Application Compliance Policy ("Last Updated: September 19th, 2024"):

> "Any functionality that provides trade suggestions, signals, or portfolio analysis must be 'pull-based'."

> "Automated orders are acceptable as long as they are managed by a rules-based and non-stochastic approach."

> "Automated orders are not acceptable if it appears to be a blanket grant of trading authority" (unless the app is registered to do so).

> "Fully managed services may be deemed acceptable if the application is a registered investment advisor."

> "SnapTrade reserves the right to shut off access to the API for non-compliance."

End User Terms ("last updated January 8, 2025"): "SnapTrade does not provide investment advisory services or brokerage services in any manner or form." and "The ownership of any investment decision(s) shall exclusively vest with you". (V)

### 3.3 What it means

- **First slice: I.** BAM trading his own Alpaca paper account through the Trading API is what the paper account is for ("Anyone globally can create an Alpaca Paper Only Account!"). Nothing fetched restricts it. If BAM later connects his own real brokerage through SnapTrade for a read-only view, that is the "Personal" use SnapTrade describes ("An individual using SnapTrade for their own brokerage accounts"), and the free plan permits "personal use".
- **Later slice: I.** Each of these changes the picture:
  1. **SnapTrade's free plan cannot serve other users.** It is "for testing and personal use only" and one Connected User. Serving other people needs Pay-as-You-Go (Launch) or Custom, KYC, and the End User Terms assent flow.
  2. **Signals must be "pull-based"** under SnapTrade's policy, even for a read-only app. The user must ask for them; the app may not push them.
  3. **Placing trades for users** needs either the user's own direct action per order, or a rules-based automation that is not "a blanket grant of trading authority". A "fully managed" design needs an RIA under SnapTrade's policy.
  4. **On Alpaca,** an app that trades other people's live accounts through their own Trading API keys runs into Section 10 (no one trades for an account without Alpaca-approved trading authorization) and Section 5(c) (POA). Alpaca's product for apps serving end users is the Broker API, whose listed use cases are broker-dealers and RIAs. Whether a non-registered "technology partner" setup fits Invest.WitUS is a question for Alpaca and a securities lawyer.
  5. **Paper only, for other users,** is a different case. Each user would hold their own paper account, and nothing real is traded. Whether signals on paper accounts are still "advice" under the Act is not answered by any fetched source. Lawyer question.

---

## 4. Market data: may the app show data to other users?

**Plain answer.** Not on the free or individual plans. Massive's Stocks plans are labeled "Individual use" and "Non-pros only". Its Market Data Terms forbid building "an application intended for use by end users other than you" and forbid redistributing or displaying the data to third parties. Showing data to other people needs Massive's Businesses Terms, which allow display to "Authorized Users or Edge Users within products" but make the customer responsible for exchange (third-party) agreements, reporting and attribution. Alpaca paper accounts get IEX data only, and the customer agreement bars distributing Alpaca's market data without written consent.

### 4.1 Massive (V)

Pricing page: Stocks Basic is $0 with 5 API calls per minute and 2 years of history; the Stocks plans are marked "Individual use", the tier links to "Non-pros only", and business use links to separate business pricing. (V)

Individuals Terms of Service ("Last Updated: July 18, 2025"), Section 2: use is "solely for your own personal, non-commercial, and non-business purposes." Section 1: "Market Data is provided to you subject to the terms and conditions of the Market Data Terms of Service" "which are incorporated herein by reference". Section 3.3 forbids "sharing an account or API keys with others." (V)

Market Data Terms of Service ("Last Updated: August 28, 2025"):

- Section 1: "you may not use the Market Data to build an application intended for use by end users other than you."
- Section 3: "Non-Professional" is "any natural person who receives market data solely for their own personal, non-business use."; "Any use of Market Data for business, professional, or other commercial purposes is incompatible with Non-Professional status."
- Section 5(c): the subscriber may not "Redistribute, display, disseminate, duplicate, license, sublicense, publish, broadcast, transmit" the data or derived works to third parties.
- Section 2: unless a separate agreement says otherwise, "any and all Market Data is strictly for display use only."
- Section 4: the subscriber enters exchange agreements, including the "OPRA Non-Professional Subscriber Agreement" and the NYSE "Agreement for Market Data Display Services"; the NYSE schedule says "Subscriber shall not furnish Market Data to any other person or entity."

Businesses Terms of Service ("Last Updated: October 6, 2026"):

- Section 2.2 grants rights "solely (a) for Customer's internal business purposes" and (b) to display Information "to Authorized Users or Edge Users within products".
- Section 6.1(d) bars making Information available "to anyone other than Customer, its Authorized Users, or its Edge Users", or giving access "as a data feed, file."
- Section 2.5(a): the Customer "is solely responsible for accessing, obtaining, entering into, and complying with" Third-Party Agreements; Massive "may assist Customer in obtaining additional licenses."
- Section 7.2: where "a Third-Party Agreement requires Customer to report usage, Edge Users, or other billing metrics", the Customer must report them.
- Section 6.1(g): the Customer may not fail "to display with any Information the attribution" a Third-Party Provider requires.

### 4.2 Alpaca market data (V)

Paper trading docs: "As an Alpaca Paper Only Account holder, you are only entitled to receive and make use of IEX market data." Market data docs: "The **Basic** plan serves as the default option for both Paper and Live trading accounts", with "for equities only the IEX exchange" on Basic and historical limits of "latest 15 minutes" on Basic. The market data docs page says nothing about redistribution.

Customer Agreement (market data clause): "AlpacaDB, Inc. provides market data to non-professional Alpaca customers." and "I agree not to reproduce, distribute, sell or commercially exploit the market data in any manner without written consent from Alpaca." (V)

SnapTrade Developer Terms: the Client will not "store, resell, or redistribute Market Data passed over the SnapTrade API." (V)

### 4.3 What it means

- **First slice: I.** BAM using Massive Stocks Basic or Alpaca IEX data in his own app for himself fits "personal, non-business use". A public waitlist page must not show live or stored market data (no price tables, no charts of real quotes), because that would "display" data to third parties.
- **Teaching material: I.** Screenshots or tables of real prices inside a Learn.WitUS lesson are display to third parties. Use synthetic or clearly licensed data in lessons, or check with the vendor first.
- **Later slice: I.** Showing prices or signals derived from vendor data to other users needs a business license (Massive Businesses Terms plus the exchange agreements it points to) or Alpaca's written consent. A cheaper design: each user brings their own data key under their own individual account, so the app never redistributes. Whether a computed signal ("buy X") counts as a "derived work" of the data under Section 5(c) is a question for the vendor and a lawyer.

---

## 5. Rules a learner must know that the app should surface

**Plain answer.** The pattern day trader rule and its $25,000 minimum have been replaced. The SEC approved FINRA's change on April 14, 2026; Alpaca says it applied the new intraday margin rules on June 4, 2026, and lowered the equity needed for 4x intraday buying power to $2,000. FINRA allowed firms an 18-month phase-in, so other brokers may still apply the old rule. SIPC covers up to $500,000 per customer including $250,000 cash, never market losses. The wash-sale rule disallows a loss when substantially identical stock is bought within 30 days before or after the sale, including in an IRA. The app should teach all four, dated, and must not teach the $25,000 rule as current.

### 5.1 Pattern day trader rule, replaced (V)

SEC Release No. 34-105226, *Order Granting Accelerated Approval of a Proposed Rule Change, as Modified by Amendment No. 1, to Amend FINRA Rule 4210 (Margin Requirements) to Replace the Day Trading Margin Provisions with Intraday Margin Standards*, April 14, 2026 (Federal Register public-inspection copy, FR Doc. 2026-07485, publication date April 17, 2026):

- The old rule, as the order describes it: "A 'pattern day trader' means any customer who executes four or more day trades within five business days." and "Minimum equity of $25,000 is required for the account of the customer deemed to be a pattern day trader".
- The change: "The proposed rule change would, among other things, eliminate provisions relating to 'pattern day traders,' the computation and use of 'day-trading buying power,' and the minimum equity requirement of $25,000 for pattern day traders, and would implement instead new intraday margin standards."
- Timing: FINRA "would issue a Regulatory Notice announcing an effective date of 45 days from the publication of that Regulatory Notice", and members "that need more time to implement the new requirements are permitted to phase-in implementation over a period of 18 months following the publication of the Regulatory Notice."
- "IT IS THEREFORE ORDERED ... that the proposed rule change (SR-FINRA-2025-017), as modified by Amendment No. 1, be, and hereby is, approved on an accelerated basis."

The proposal itself is in the Federal Register, 91 FR 1580 (January 14, 2026), Release No. 34-104572, via govinfo. (V)

Alpaca blog, "FINRA Retires the PDT Rule" (April 27, 2026; "Last updated Thursday, June 4, 2026"): "We have officially lifted the Pattern Day Trader rule"; "Intraday Buying Power replaces Day Trade Buying Power"; "the minimum equity requirement for 4x intraday buying power has been lowered from $25,000 to $2,000"; an account that repeatedly fails intraday margin calls "may be restricted for up to 90 calendar days." The post gives FINRA's effective date as June 4, 2026. (V; vendor statement)

Alpaca docs, "The Intraday Margin Rule": "The specific $25,000 equity minimum required to day trade has been removed." "Brokers are no longer required to track 'round-trip' counts." (V)

The FINRA Regulatory Notice itself (26-10) and the current Rule 4210 page were not reachable (see "Not reachable"). The June 4, 2026 effective date therefore rests on Alpaca's page, not FINRA's. Inference (I): if FINRA's notice was published April 20, 2026 (a date reported by secondary sources, not verified here), 45 days later is June 4, 2026, which matches Alpaca, and the 18-month phase-in would end about October 20, 2027.

FINRA investor page, "Frequent Intraday Trading: Understanding the Basics": "you must maintain a minimum of $2,000 in equity in your margin account." It also says repeated unmet intraday margin deficits can lead the firm to freeze margin trading for up to 90 days. (V)

### 5.2 SEC day-trading risk page (V)

SEC, "Day Trading: Your Dollars at Risk" (published April 2005): "Day traders typically suffer severe financial losses in their first months of trading." and "Borrowing money to trade in stocks is always a risky business." The page also says day traders "do not 'invest'". (V)

### 5.3 SIPC (V)

SIPC, "What SIPC Protects": "The limit of SIPC protection is $500,000, which includes a $250,000 limit for cash." and "SIPC does not protect against the decline in value of your securities." The page does not mention paper trading. (V) Inference (I): a paper account holds no real money or securities, so SIPC has nothing to protect there.

### 5.4 Wash sales and tax-loss harvesting (V)

IRS Publication 550 (2025), "Wash Sales":

> "A wash sale occurs when you sell or trade stock or securities at a loss and within 30 days before or after the sale you: Buy substantially identical stock or securities, Acquire substantially identical stock or securities in a fully taxable trade, Acquire a contract or option to buy substantially identical stock or securities, or Acquire substantially identical stock for your individual retirement arrangement (IRA) or Roth IRA."

> "You cannot deduct losses from sales or trades of stock or securities in a wash sale"

The disallowed loss is added to the basis: "add the disallowed loss to the cost of the new stock or securities" (this does not apply to the IRA case). "Your holding period for the new stock or securities includes the holding period of the stock or securities sold."

Inference (I): tax-loss harvesting sells a loser to book the loss. If the app's method then rebuys the same stock (or something "substantially identical") within the 61-day window, or the user buys it in an IRA, the loss is disallowed. A momentum method that sells and later rebuys the same names can trip this. Whether two different funds tracking the same index are "substantially identical" is not answered by the publication text read; that is a tax adviser's question.

Note: Alpaca's "Preventing Wash Trades" protection ("A wash trade happens when a customer buys and sells the same security at the same time") is about self-matching orders, a different thing from the tax wash-sale rule. The app should not confuse the two. (V)

### 5.5 What it means

- **First slice: I.** These rules cost nothing to show and fit the "method adherence" core: show the date-stamped rule beside the button that could break it (a sell-and-rebuy inside 30 days; a margin warning). Paper accounts trigger no tax and no SIPC question, so lessons should say so plainly.
- **Later slice: I.** Users on real accounts at other brokers (through SnapTrade) may be at a firm still in its phase-in, so the app should not state the margin rule as uniform. Teach "check your broker's current rule" with the April 14, 2026 SEC order as the source.

---

## 6. Privacy of money data (gate G4)

**Plain answer.** The Gramm-Leach-Bliley Act reaches "financial institutions": businesses engaged in activities that are financial in nature under the Bank Holding Company Act. The FTC says that includes companies offering "financial or investment advice" and lists "investment advisors not required to register with the SEC" and "finders". An app run only on its owner's data has no consumers. An app that gives other people investment advice, or brings buyers and sellers together, may become one; that is a lawyer's question. The Indiana Consumer Data Protection Act applies only at 100,000 Indiana consumers a year (or 25,000 plus more than half of revenue from selling data), and does not apply to GLBA financial institutions or GLBA data. SnapTrade's developer terms add contract duties regardless: a 24-hour breach notice to SnapTrade, secure storage, deletion on request.

### 6.1 Gramm-Leach-Bliley Act and the Safeguards Rule (V)

15 U.S.C. 6809(3)(A): "The term 'financial institution' means any institution the business of which is engaging in financial activities as described in section 1843(k) of title 12." 15 U.S.C. 6809(4)(A): "nonpublic personal information" means "personally identifiable financial information" provided by a consumer to a financial institution, resulting from a transaction or service, or otherwise obtained. (V)

16 CFR 314.2(h)(1) (Safeguards Rule, eCFR): "Financial institution means any institution the business of which is engaging in an activity that is financial in nature or incidental to such financial activities as described in section 4(k) of the Bank Holding Company Act of 1956, 12 U.S.C. 1843(k). An institution that is significantly engaged in financial activities, or significantly engaged in activities incidental to such financial activities, is a financial institution." (V)

16 CFR 314.2(e)(2)(i)(G) gives as an example of a continuing customer relationship a consumer who "Obtains financial, investment, or economic advisory services from you for a fee". (V)

FTC, "Gramm-Leach-Bliley Act" business guidance page: the Act applies to "companies that offer consumers financial products or services like loans, financial or investment advice, or insurance." The Safeguards Rule "requires covered companies to develop, implement, and maintain an information security program" with "administrative, technical, and physical safeguards designed to protect customer information." (V)

FTC, "FTC Safeguards Rule: What Your Business Needs to Know" (December 2024): examples of covered entities include "investment advisors not required to register with the SEC" and, since 2021, "finders" (companies that bring buyers and sellers together). Certain provisions do not apply to institutions that "maintain customer information concerning fewer than five thousand consumers." A "notification event" is "a security breach involving the unauthorized acquisition of at least 500 consumers' unencrypted information", reported to the FTC no later than 30 days after discovery. (V)

### 6.2 Indiana Consumer Data Protection Act (V)

IC 24-15-1-1(a) (Indiana Code 2026): the article "applies to a person that conducts business in Indiana or produces products or services that are targeted to residents of Indiana and that during a calendar year: (1) controls or processes personal data of at least one hundred thousand (100,000) consumers who are Indiana residents; or (2) controls or processes personal data of at least twenty-five thousand (25,000) consumers who are Indiana residents and derives more than fifty percent (50%) of gross revenue from the sale of personal data."

IC 24-15-1-1(b)(2): the article does not apply to "Any financial institutions and affiliates, or data subject to Title V of the federal Gramm-Leach-Bliley Act (15 U.S.C. 6801 et seq.)."

IC 24-15-2 defines "Consumer" as an individual who "is a resident of Indiana" and "is acting only for a personal, family, or household purpose"; it excludes "an individual acting in a commercial or employment context." (V)

Indiana Attorney General, *Consumer Data Protection Bill of Rights* (PDF): "Starting January 1, 2026, we will enforce Indiana's new Consumer Data Protection Act (CDPA)." and the thresholds as above. (V)

### 6.3 What it means

- **First slice: I.** BAM's own paper account data, plus waitlist emails. GLBA's definitions turn on serving consumers; there are none. The Indiana CDPA thresholds are far above a waitlist. G4 still applies under the rubric because the app holds broker keys: keep Alpaca keys server-side only, paper keys by default, no real-money keys in the first slice, and write the incident plan.
- **Later slice: I.** If Invest.WitUS gives other people investment advice for a fee, the FTC's own examples ("investment advisors not required to register with the SEC") suggest the Safeguards Rule could apply, which means a written information security program and the FTC breach notice at 500 consumers. Whether a free method-adherence app is "significantly engaged" in a financial activity is a question for a lawyer. Regardless of GLBA, SnapTrade's terms require secure storage, deletion on request, and notice to SnapTrade "within 24 hours of any breach". Indiana's CDPA is not reached until 100,000 Indiana consumers, and would not apply at all to a GLBA financial institution.
- **Students: I.** Minors' data raises separate rules (COPPA under 13, school privacy agreements) that this slice did not research; see open questions.

---

## 7. Advertising and testimonials

**Plain answer.** The SEC Marketing Rule binds only advisers "registered or required to be registered" under section 203; it does not reach the first slice. The FTC Endorsement Guides apply to any advertiser: endorsements must be honest, endorsers who claim to use the product must be bona fide users, a testimonial about results implies typical results unless the ad discloses what is generally expected, and material connections (pay, free access, early access) must be disclosed.

### 7.1 SEC Marketing Rule (V)

17 CFR 275.206(4)-1 (eCFR): "it is unlawful for any investment adviser registered or required to be registered under section 203 of the Act (15 U.S.C. 80b-3), directly or indirectly, to disseminate any advertisement that violates any of paragraphs (a) through (d) of this section."

Paragraph (a)(4): an advertisement may not "Discuss any potential benefits to clients or investors connected with or resulting from the investment adviser's services or methods of operation without providing fair and balanced treatment of any material risks or material limitations associated with the potential benefits".

Paragraph (b): no testimonial or endorsement unless the adviser meets (b)(1) to (3), including disclosure "Clearly and prominently" that the testimonial was given by a current client, whether "cash or non-cash compensation was provided", and "any material conflicts of interest". Paragraph (e)(1) defines "advertisement" to include communications with "hypothetical performance". (V)

Inference (I): a state-registered adviser is not registered "under section 203", but "required to be registered" may still apply depending on facts; and Indiana has its own rules for state advisers that this slice did not fetch. Lawyer question.

### 7.2 FTC Endorsement Guides (V)

16 CFR 255.1(a): "Endorsements must reflect the honest opinions, findings, beliefs, or experience of the endorser." 255.1(c): "When the advertisement represents that the endorser uses the endorsed product, the endorser must have been a bona fide user of it at the time the endorsement was given."

16 CFR 255.2(b): an endorsement about a key attribute "will likely be interpreted as representing that the endorser's experience is representative of what consumers will generally achieve"; without substantiation, "the advertisement should clearly and conspicuously disclose the generally expected performance in the depicted circumstances".

16 CFR 255.5(a): a material connection "must be disclosed clearly and conspicuously"; connections include "monetary payment or the provision of free or discounted products" and "early access to a product". (V)

FTC, "FTC's Endorsement Guides: What People Are Asking": "The FTC Act applies across the board." On fake engagement: "they are clearly deceptive". (V)

### 7.3 What it means

- **First slice: I.** The waitlist page should carry no testimonials (there are no users yet) and no performance claims. Any paper-trading result shown is hypothetical and should say so, with the paper limits Alpaca lists (no dividends, slippage or fees). Do not imply returns.
- **Later slice: I.** Testimonials from beta users who got free or early access must disclose that connection (255.5 names "early access"). Any "I made X%" testimonial implies typical results under 255.2(b). If BAM ever becomes a registered or required-to-be-registered adviser, the Marketing Rule's "fair and balanced" and testimonial conditions apply on top.

---

## Summary table

| Question | First slice: owner's own money (paper, waitlist) | Later slice: other users | Source |
|---|---|---|---|
| 1. Adviser definition | Outside the words: no "others", no "compensation" (I) | Signals or trades for others for pay match the words; Indiana registration, Series 65, Form ADV likely; lawyer decides (I) | 15 U.S.C. 80b-2(a)(11), 80b-3a; IC 23-19-1-2(15), 23-19-4-3; SEC IM 2017-02 (V) |
| 2. What needs no registration | Own money; general lessons (I) | Same signals published to all on a schedule resemble *Lowe*; per-account signals or trades do not; lawyer decides (I) | 80b-2(a)(11)(B), (D); *Lowe v. SEC* (V) |
| 3. Power to place trades | Alpaca paper account for self: permitted (V, I) | SnapTrade free plan: personal use, 1 user only; signals must be "pull-based"; no blanket trading authority; managed service needs RIA; Alpaca requires approved trading authorization; Broker API for apps serving others (V) | Alpaca Customer Agreement; SnapTrade Developer Terms, Compliance Policy (V) |
| 4. Market data | Personal use fine; no data on the public waitlist (I) | Massive individual plans forbid apps for others; business terms plus exchange agreements needed; Alpaca data not to be distributed without consent (V) | Massive Market Data Terms, Businesses Terms; Alpaca Customer Agreement (V) |
| 5. Learner rules | Teach: PDT $25,000 rule replaced (2026), SIPC $500k/$250k, wash sale 30 days; paper has no tax or SIPC effect (V, I) | Brokers may be mid phase-in to Oct 2027; say "check your broker" (I) | SEC Release 34-105226; Alpaca docs; SIPC; IRS Pub. 550 (V) |
| 6. Privacy | No consumers; CDPA not reached; still protect keys (I) | Possible GLBA Safeguards duties if advice for a fee; SnapTrade 24-hour breach notice; CDPA at 100,000 Indiana consumers, and not for GLBA institutions (V, I) | 15 U.S.C. 6809; 16 CFR 314.2; FTC pages; IC 24-15-1-1 (V) |
| 7. Advertising | FTC Guides apply; no testimonials, no performance claims on the waitlist (I) | Disclose early-access and paid connections; results imply typical; Marketing Rule only if an adviser (V) | 16 CFR 255; 17 CFR 275.206(4)-1 (V) |

**Bearing on the rubric (I).** G6: the first slice is not blocked by any rule read. The later slice is not blocked either, but its design (signals pushed versus pulled, per-account versus general, auto-trading versus user-placed, paid versus free) decides whether registration applies; G6 resolves only with a securities lawyer's answer. G4: the first slice resolves with written mitigations (keys server-side, paper only, incident plan). D9 for the later slice sits near 1 to 2 until the lawyer answers; near 3 to 4 for the first slice.

---

## Not reachable

| Source wanted | What happened | Used instead |
|---|---|---|
| uscode.house.gov, 15 U.S.C. 80b-2 and 80b-3a | HTTP 404 on the two URL forms tried (not a bot block) | govinfo.gov U.S. Code 2024 edition HTML for 80b-2, 80b-3a, 6809 |
| eCFR web pages (ecfr.gov/current/...) | 302 redirect to unblock.federalregister.gov (bot check); not bypassed | eCFR versioner API (`/api/versioner/v1/full/2026-10-23/...`), which required a compression header |
| FINRA Rule 4210 page (finra.org) | HTTP 429, then a "Just a moment..." bot check (403) | SEC Release 34-105226 (public-inspection.federalregister.gov) and 91 FR 1580 (govinfo) |
| FINRA Regulatory Notice 26-10 (page and PDF) | HTTP 429 and 403 bot check | Same SEC order; Alpaca's docs and blog for the June 4, 2026 date (vendor statement) |
| sec.gov Release 34-104572 PDF | HTTP 403 | govinfo Federal Register copy, 91 FR 1580 |
| investor.gov day-trading glossary | HTTP 403 | SEC "Day Trading: Your Dollars at Risk" page on sec.gov (reached) |
| iga.in.gov `/laws/...` pages | JavaScript app; no text served | iga.in.gov "Indiana Code 2026" PDFs for IC 23-19 and IC 24-15 |
| law.justia.com (Indiana Code copies) | HTTP 403 | Official iga.in.gov PDFs |
| legiscan.com SB 5 text | HTTP 403 | Official iga.in.gov PDF of IC 24-15 |
| web.archive.org | Fetch tool cannot reach the site | Not needed after the iga.in.gov PDFs |
| snaptrade.com/terms-of-service | HTTP 404 (wrong path) | snaptrade.com/developer-terms-of-use and /terms-and-conditions |
| Indiana AG Consumer Protection Division page | Reached, but no CDPA text on it | AG *Consumer Data Protection Bill of Rights* PDF |

The SEC IM Guidance Update 2017-02 PDF was reached; the fetch tool could not read its compressed text, so the downloaded file was extracted locally.

---

## Open questions for a lawyer

1. **Signals versus advice.** If Invest.WitUS publishes each taught method's rules and the resulting buy/sell list to every user the same way, on a fixed schedule, does it fall within the publisher exclusion as *Lowe* read it? Does that change if the list is computed against each user's own holdings?
2. **Compensation.** Is a free app with a paid tier, a donation, a course fee in Learn.WitUS or ElementaryMBA, or a sponsorship "compensation" for advice delivered by the app?
3. **Paper accounts.** Are signals or automated orders on other users' paper (simulated) accounts "advice as to the advisability of ... purchasing, or selling securities"?
4. **Auto-trading.** Under the Act and IC 23-19, does a user-configured, rules-based order on the user's own account (SnapTrade's "rules-based and non-stochastic" test) differ from discretionary management?
5. **Teacher exclusion.** Does the "teacher ... solely incidental" exclusion cover an app used in a course that signals trades on students' own accounts?
6. **Indiana.** If registration is needed, is it Indiana state registration (Form ADV, Series 65 representative, $100 fee), and does any Indiana rule or order exempt an education-first tool?
7. **Alpaca.** Can a non-registered "technology partner" use Broker API for Invest.WitUS, or does serving other people's live accounts require a broker-dealer or RIA?
8. **GLBA.** Would a free method-adherence app that reads users' holdings through SnapTrade be a "financial institution" under 16 CFR 314.2(h)?
9. **Market data.** Is a computed signal derived from Massive or Alpaca data a "derived work" that may not be shown to others under an individual plan?
10. **Minors.** May students under 18 use the app with their own (custodial) or paper accounts, and what do COPPA and school data agreements require? Not researched in this slice.
11. **Marketing.** Do Indiana's rules for state-registered advisers impose advertising or testimonial limits like the SEC Marketing Rule?

---

## References

Alpaca. (n.d.-a). *About Broker API*. Alpaca Docs. https://docs.alpaca.markets/docs/about-broker-api (retrieved October 27, 2026)

Alpaca. (n.d.-b). *About market data API*. Alpaca Docs. https://docs.alpaca.markets/docs/about-market-data-api (retrieved October 27, 2026)

Alpaca. (n.d.-c). *Alpaca customer agreement* (Version V26.2026.07). https://files.alpaca.markets/disclosures/library/AcctAppMarginAndCustAgmt.pdf (retrieved October 27, 2026)

Alpaca. (n.d.-d). *Alpaca terms and conditions*. https://files.alpaca.markets/disclosures/library/TermsAndConditions.pdf (retrieved October 27, 2026)

Alpaca. (n.d.-e). *Broker API*. https://alpaca.markets/broker-api (retrieved October 27, 2026)

Alpaca. (n.d.-f). *Disclosures and agreements*. https://alpaca.markets/disclosures (retrieved October 27, 2026)

Alpaca. (n.d.-g). *Paper trading*. Alpaca Docs. https://docs.alpaca.markets/docs/paper-trading (retrieved October 27, 2026)

Alpaca. (n.d.-h). *The intraday margin rule*. Alpaca Docs. https://docs.alpaca.markets/us/docs/the-intraday-margin-rule (retrieved October 27, 2026)

Alpaca. (n.d.-i). *Trading API*. Alpaca Docs. https://docs.alpaca.markets/docs/trading-api (retrieved October 27, 2026)

Alpaca. (n.d.-j). *User protection*. Alpaca Docs. https://docs.alpaca.markets/docs/user-protection (retrieved October 27, 2026)

Alpaca. (2026, April 27). *FINRA retires the PDT rule: Introducing Alpaca's new intraday margin framework*. https://alpaca.markets/blog/finra-retires-the-pdt-rule-introducing-alpacas-new-intraday-margin-framework/ (retrieved October 27, 2026)

Federal Trade Commission. (n.d.-a). *FTC's endorsement guides: What people are asking*. https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking (retrieved October 27, 2026)

Federal Trade Commission. (n.d.-b). *Gramm-Leach-Bliley Act*. https://www.ftc.gov/business-guidance/privacy-security/gramm-leach-bliley-act (retrieved October 27, 2026)

Federal Trade Commission. (2024, December). *FTC Safeguards Rule: What your business needs to know*. https://www.ftc.gov/business-guidance/resources/ftc-safeguards-rule-what-your-business-needs-know (retrieved October 27, 2026)

Financial Industry Regulatory Authority. (n.d.). *Frequent intraday trading: Understanding the basics*. https://www.finra.org/investors/investing/investment-products/stocks/day-trading (retrieved October 27, 2026)

Guides Concerning the Use of Endorsements and Testimonials in Advertising, 16 C.F.R. pt. 255 (2026). https://www.ecfr.gov/api/versioner/v1/full/2026-10-23/title-16.xml?part=255 (retrieved October 27, 2026)

Indiana Attorney General. (n.d.). *Indiana Consumer Data Protection Act (CDPA): Consumer bill of rights*. https://www.in.gov/attorneygeneral/files/Indiana-Consumer-Data-Protection_Consumer-Bill-of-Rights_CDPCBOR.pdf (retrieved October 27, 2026)

Indiana Consumer Data Protection, Ind. Code § 24-15 (2026). https://iga.in.gov/ic/2026/Title_24/Article_15.pdf (retrieved October 27, 2026)

Indiana Secretary of State, Securities Division. (n.d.). *Investment adviser: General information*. https://securities.sos.in.gov/general-information/investment-adviser/ (retrieved October 27, 2026)

Indiana Uniform Securities Act, Ind. Code § 23-19 (2026). https://iga.in.gov/ic/2026/Title_23/Article_19.pdf (retrieved October 27, 2026)

Internal Revenue Service. (2026). *Publication 550 (2025), Investment income and expenses*. https://www.irs.gov/publications/p550 (retrieved October 27, 2026)

Investment adviser marketing, 17 C.F.R. § 275.206(4)-1 (2026). https://www.ecfr.gov/api/versioner/v1/full/2026-10-23/title-17.xml?part=275&section=275.206(4)-1 (retrieved October 27, 2026)

Eligibility for SEC registration; Switching to or from SEC registration, 17 C.F.R. § 275.203A-1 (2026). https://www.ecfr.gov/api/versioner/v1/full/2026-10-23/title-17.xml?part=275&section=275.203A-1 (retrieved October 27, 2026)

Lowe v. Securities and Exchange Commission, 472 U.S. 181 (1985). https://www.law.cornell.edu/supremecourt/text/472/181 (retrieved October 27, 2026)

Massive. (n.d.). *Pricing*. https://massive.com/pricing (retrieved October 27, 2026)

Massive. (2025a, July 18). *Individuals terms of service*. https://massive.com/legal/individuals-terms-of-service (retrieved October 27, 2026)

Massive. (2025b, August 28). *Market data terms of service*. https://massive.com/legal/market-data-terms-of-service (retrieved October 27, 2026)

Massive. (2026, October 6). *Businesses terms of service*. https://massive.com/legal/businesses-terms-of-service (retrieved October 27, 2026)

Securities and Exchange Commission. (2005, April 20). *Day trading: Your dollars at risk*. https://www.sec.gov/investor/pubs/daytips.htm (retrieved October 27, 2026)

Securities and Exchange Commission. (2026a). Self-regulatory organizations; Financial Industry Regulatory Authority, Inc.; Notice of filing of a proposed rule change to amend FINRA Rule 4210 (margin requirements) to replace the day trading margin provisions with intraday margin standards (Release No. 34-104572). *Federal Register, 91*(9), 1580-1589. https://www.govinfo.gov/content/pkg/FR-2026-01-14/html/2026-00519.htm (retrieved October 27, 2026)

Securities and Exchange Commission. (2026b). *Self-regulatory organizations; Financial Industry Regulatory Authority, Inc.; Notice of filing of Amendment No. 1 and order granting accelerated approval of a proposed rule change, as modified by Amendment No. 1, to amend FINRA Rule 4210 (margin requirements) to replace the day trading margin provisions with intraday margin standards* (Release No. 34-105226; FR Doc. 2026-07485). https://public-inspection.federalregister.gov/2026-07485.pdf (retrieved October 27, 2026)

Securities and Exchange Commission, Division of Investment Management. (2017). *Robo-advisers* (IM Guidance Update No. 2017-02). https://www.sec.gov/investment/im-guidance-2017-02.pdf (retrieved October 27, 2026)

Securities Investor Protection Corporation. (n.d.). *What SIPC protects*. https://www.sipc.org/for-investors/what-sipc-protects (retrieved October 27, 2026)

SnapTrade. (n.d.-a). *Personal vs commercial*. SnapTrade Docs. https://docs.snaptrade.com/docs/personal-vs-commercial (retrieved October 27, 2026)

SnapTrade. (n.d.-b). *Pricing*. https://snaptrade.com/pricing (retrieved October 27, 2026)

SnapTrade. (2024, September 19). *Application compliance policy*. https://snaptrade.com/compliance-policy (retrieved October 27, 2026)

SnapTrade. (2025, January 8). *End user terms and conditions*. https://snaptrade.com/terms-and-conditions (retrieved October 27, 2026)

SnapTrade. (2026, May 22). *Developer terms of use*. https://snaptrade.com/developer-terms-of-use (retrieved October 27, 2026)

Standards for Safeguarding Customer Information: Definitions, 16 C.F.R. § 314.2 (2026). https://www.ecfr.gov/api/versioner/v1/full/2026-10-23/title-16.xml?part=314&section=314.2 (retrieved October 27, 2026)

State and Federal responsibilities, 15 U.S.C. § 80b-3a (2024). https://www.govinfo.gov/content/pkg/USCODE-2024-title15/html/USCODE-2024-title15-chap2D-subchapII-sec80b-3a.htm (retrieved October 27, 2026)

Definitions (Investment Advisers Act of 1940), 15 U.S.C. § 80b-2 (2024). https://www.govinfo.gov/content/pkg/USCODE-2024-title15/html/USCODE-2024-title15-chap2D-subchapII-sec80b-2.htm (retrieved October 27, 2026)

Definitions (Gramm-Leach-Bliley Act, Title V), 15 U.S.C. § 6809 (2024). https://www.govinfo.gov/content/pkg/USCODE-2024-title15/html/USCODE-2024-title15-chap94-subchapI-sec6809.htm (retrieved October 27, 2026)
