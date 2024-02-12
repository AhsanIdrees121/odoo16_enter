/** @odoo-module **/

import DialingPanel from "voip.DialingPanel";
import { DialingPanelAdapter } from "./legacy_compatibility";
import { useModels } from '@mail/component_hooks/use_models';

const { Component, xml } = owl;

/**
 * Main component to wrap the DialingPanel. Ideally, it should conditionally
 * instantiate the DialingPanel (if it is open or not). However, the legacy
 * DialingPanel does rpcs at startup, so it hasn't been designed to be created
 * and destroyed dynamically. All this could be re-tought when it will be fully
 * converted in owl (e.g. rpcs done in the service at deployment).
 */
export class DialingPanelContainer extends Component {
    setup() {
        useModels();
        this.DialingPanel = DialingPanel;
    }

    get messaging() {
        return this.env.services.messaging.modelManager.messaging;
    }
}
DialingPanelContainer.template = xml`
    <div class="o_voip_dialing_panel_container">
        <t t-if="messaging and messaging.isInitialized">
            <DialingPanelAdapter Component="DialingPanel" bus="props.bus" />
        </t>
    </div>`;
DialingPanelContainer.components = { DialingPanelAdapter };
